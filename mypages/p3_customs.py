import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


def page3():
    """3. 수입 통관 준비 – 금속류 관세/HS 조회 + AI 통관 Q&A"""

    # ---------------------------------------------------------------
    # 0) 관세율2 모듈 경로 세팅
    # ---------------------------------------------------------------
    APP_DIR = Path(__file__).resolve().parent.parent / "관세율2"
    app_dir_str = str(APP_DIR)

    original_sys_path = list(sys.path)
    if app_dir_str not in sys.path:
        sys.path.insert(0, app_dir_str)

    try:
        # 지연 임포트
        from modules.data_loader import load_tariff_data
        from modules.chroma_builder import (
            build_chroma,
            get_chroma_client,
            COLLECTION_NAME,
        )
        from modules.rag_engine import get_rag_engine

        # -----------------------------------------------------------
        # 1) 세션 상태 기본값
        # -----------------------------------------------------------
        if "p3_tariff_df" not in st.session_state:
            st.session_state.p3_tariff_df = pd.DataFrame()
        if "p3_db_ready" not in st.session_state:
            st.session_state.p3_db_ready = False
        if "p3_rag_engine" not in st.session_state:
            st.session_state.p3_rag_engine = None
        if "p3_last_result" not in st.session_state:
            st.session_state.p3_last_result = None
        if "p3_question" not in st.session_state:
            st.session_state.p3_question = ""

        # -----------------------------------------------------------
        # 2) 데이터 및 Chroma 초기화 함수
        # -----------------------------------------------------------

        @st.cache_data
        def initialize_data_p3():
            df = load_tariff_data()
            st.session_state.p3_tariff_df = df
            return df

        @st.cache_resource
        def initialize_chromadb_p3(force_rebuild: bool = False):
            client = get_chroma_client()
            existing = [c.name for c in client.list_collections()]
            if COLLECTION_NAME not in existing or force_rebuild:
                with st.spinner("📦 Chroma DB 구축 중입니다..."):
                    try:
                        build_chroma(force_rebuild=True)
                    except TypeError:
                        build_chroma()
                st.success("✅ Chroma DB 구축 완료!")
            st.session_state.p3_db_ready = True
            return True

        @st.cache_resource
        def initialize_rag_engine_p3(df):
            """df + collection → RAG 엔진 생성"""
            if not st.session_state.get("p3_db_ready", False):
                return None

            client = get_chroma_client()
            collection = client.get_collection(COLLECTION_NAME)

            engine = get_rag_engine(df, collection)
            st.session_state.p3_rag_engine = engine
            return engine

        # 실제 초기화 실행
        df = initialize_data_p3()
        if not df.empty:
            initialize_chromadb_p3()
            initialize_rag_engine_p3(df)

        # -----------------------------------------------------------
        # 3) 사이드바 – DB 새로고침
        # -----------------------------------------------------------
        with st.sidebar:
            st.header("⚙️ 관리 메뉴")
            if st.button("데이터 / DB 새로고침"):
                st.info("🔄 ChromaDB 및 캐시를 재설정합니다...")

                try:
                    client = get_chroma_client()
                    try:
                        client.reset()
                    except Exception:
                        pass
                except:
                    pass

                st.cache_data.clear()
                st.cache_resource.clear()

                for key in list(st.session_state.keys()):
                    if key.startswith("p3_"):
                        del st.session_state[key]

                st.success("완료! 페이지를 새로고침합니다.")
                st.rerun()

        # -----------------------------------------------------------
        # 4) UI 탭 구성
        # -----------------------------------------------------------
        tab1, tab2 = st.tabs(["📑 관세율표 조회", "🤖 AI 통관 Q&A"])

        # -----------------------------------------------------------
        # TAB 1 – 관세율표 조회
        # -----------------------------------------------------------
        with tab1:
            st.header("📑 금속류 관세 · HS 코드 조회")

            if st.session_state.p3_tariff_df.empty:
                st.warning("데이터가 없습니다. 관세율2/data 폴더를 확인하세요.")
            else:
                df = st.session_state.p3_tariff_df.copy()

                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    countries = ["전체"] + sorted(df["country"].dropna().unique().tolist())
                    # key를 추가하여 세션 상태에 저장
                    selected_country = st.selectbox("국가", countries, key="p3_selected_country")

                with col2:
                    hs_code_query = st.text_input("HS CODE 검색", placeholder="예: 2601")

                with col3:
                    product_query = st.text_input("품목명 검색(desc)", placeholder="예: iron / nickel")

                # 필터링
                if selected_country != "전체":
                    df = df[df["country"] == selected_country]
                if hs_code_query:
                    df = df[df["hs_code"].astype(str).str.startswith(hs_code_query)]
                if product_query:
                    for token in product_query.split():
                        df = df[df["desc"].str.contains(token, case=False, na=False)]

                st.subheader(f"📊 조회 결과: {len(df)}건")

                if not df.empty:
                    st.dataframe(
                        df[["country", "hs_code", "desc", "mfn_rate"]],
                        use_container_width=True,
                    )
                else:
                    st.info("조건에 맞는 결과가 없습니다.")

        # -----------------------------------------------------------
        # TAB 2 – AI 통관 Q&A
        # -----------------------------------------------------------
        with tab2:
            st.header("🤖 AI 통관 Q&A")

            # 안내문 추가 (RAG/Tool 역할 요약)
            st.markdown(
                """
                ### 🔍 이 Q&A는 무엇을 할 수 있나요?
                - **RAG 검색**: 각국 금속류 관세 데이터를 기반으로 최적의 정보를 찾아드립니다.  
                - **Hybrid Search**: 키워드 + 벡터 검색을 결합하여 정확도를 높였습니다.  
                - **ToolCall**  
                    - `TOOL_SEARCH_TARIFF`: 국가 + 품목 기반 MFN 관세 자동 조회  
                    - `TOOL_CALCULATE`: CIF + 세율 기반 관세 계산  

                아래 입력창에 자연어로 질문하면 자동으로 라우팅하여 최적의 방식으로 답변합니다.
                """
            )

            if st.session_state.p3_rag_engine is None:
                st.warning("RAG 엔진이 아직 준비되지 않았습니다.")
            else:
                # 새로운 예시 문구
                st.info(
                    """
                    ** 추천 질문 예시 광석 이름은 영어로 기입해야 검색이 원활합니다.**
                    - "일본에서 nickel 수입 시 MFN 관세율은 몇 %인가요?"
                    - "미국으로 iron ore을 수출할 때 적용될 HS Code와 MFN 세율을 알려줘."
                    - "과세가격이 30,000달러이고 MFN 세율이 8%일 때, 예상 관세액은?"
                    - "HS Code 2604.00 품목은 뭐야?"
                    """
                )

                # 예시 버튼 1개만 유지 (부담 예시)
                col1, col2, col3 = st.columns(3)
                with col1:
                    pass  # 버튼 삭제
                with col2:
                    pass  # 버튼 삭제
                with col3:
                    if st.button("💰 계산 toolcall"):
                        st.session_state.p3_question = (
                            "MFN 10%에 CIF 20000달러면 관세 얼마나 나와?"
                        )

                # 입력창
                question = st.text_area(
                    "질문 입력",
                    value=st.session_state.get("p3_question", ""),
                    height=90,
                    placeholder="예: 일본에서 nickel 수입 시 MFN 세율은?",
                )

                if st.button("질문하기", type="primary"):
                    if not question.strip():
                        st.warning("질문을 입력하세요.")
                    else:
                        with st.spinner("AI 답변 생성 중…"):
                            result = st.session_state.p3_rag_engine.generate_answer(question)
                        st.session_state.p3_last_result = result

                        # --- FIX: customs_risk를 st.session_state에 저장 ---
                        analysis = result.get("analysis", {})
                        mfn_rate = analysis.get('mfn_rate')

                        if mfn_rate is not None:
                            try:
                                mfn_rate_float = float(mfn_rate)
                                if mfn_rate_float > 8.0:
                                    risk_level = "high"
                                elif mfn_rate_float > 3.0:
                                    risk_level = "medium"
                                else:
                                    risk_level = "low"
                                
                                customs_risk_data = {
                                    "mfn_rate": mfn_rate_float,
                                    "risk_level": risk_level,
                                    "question": question,
                                    "answer": result.get("answer", "")
                                }
                                st.session_state["customs_risk"] = customs_risk_data
                            except (ValueError, TypeError):
                                pass # mfn_rate를 float으로 변환하지 못하는 경우 무시
                        # --- END FIX ---

                result = st.session_state.get("p3_last_result")

                if result:
                    st.markdown("---")
                    st.subheader("🧠 에이전트 분석 결과")
                    st.json(result.get("analysis", {}))

                    st.subheader("💬 답변")
                    st.markdown(result.get("answer", ""))

                    st.subheader("📚 참고 데이터")
                    sources = result.get("sources") or []
                    if isinstance(sources, list) and sources:
                        st.dataframe(pd.DataFrame(sources))
                    else:
                        st.info("참고 데이터 없음")

    finally:
        sys.path[:] = original_sys_path

# -----------------------------------------------------------
# 🔹 p8_agent가 호출할 실행 전용 함수
# -----------------------------------------------------------
def _get_rag_engine_for_agent():
    """p8_agent 전용 RAG 엔진 초기화 함수 (UI 및 캐시 미사용)"""
    APP_DIR = Path(__file__).resolve().parent.parent / "관세율2"
    app_dir_str = str(APP_DIR)

    original_sys_path = list(sys.path)
    if app_dir_str not in sys.path:
        sys.path.insert(0, app_dir_str)
    
    try:
        from modules.data_loader import load_tariff_data
        from modules.chroma_builder import build_chroma, get_chroma_client, COLLECTION_NAME
        from modules.rag_engine import get_rag_engine

        # 1. 데이터 로드
        df = load_tariff_data()
        if df.empty:
            raise ValueError("관세 데이터를 로드하지 못했습니다.")

        # 2. ChromaDB 준비
        client = get_chroma_client()
        existing = [c.name for c in client.list_collections()]
        if COLLECTION_NAME not in existing:
            print(f"ChromaDB 컬렉션({COLLECTION_NAME})이 없어 새로 구축합니다.")
            try:
                build_chroma(force_rebuild=True)
            except TypeError:
                build_chroma()
        
        collection = client.get_collection(COLLECTION_NAME)
        
        # 3. RAG 엔진 생성
        engine = get_rag_engine(df, collection)
        return engine

    finally:
        sys.path[:] = original_sys_path


def run_p3_customs(state: dict) -> dict:
    """p8_agent를 위한 통관/관세 리스크 분석 실행 함수"""
    try:
        # 3번 페이지 UI에서 사용자가 선택한 국가를 우선적으로 사용
        origin_country = st.session_state.get('p3_selected_country', '중국')
        if origin_country == "전체": # '전체'가 선택된 경우 기본값으로
            origin_country = '중국'
        
        # 1. RAG 엔진 가져오기
        rag_engine = _get_rag_engine_for_agent()
        if rag_engine is None:
            return {"error": "RAG 엔진을 초기화하지 못했습니다."}

        # 2. 표준 질문 실행
        question = f"{origin_country}에서 니켈(nickel) 수입 시 MFN 관세율은 몇 %인가요?"
        result = rag_engine.generate_answer(question)
        
        # 3. 결과 파싱 및 리스크 분석 (page3 UI와 동일한 방식으로 수정)
        analysis = result.get("analysis", {})
        mfn_rate = analysis.get('mfn_rate') # <-- 구조화된 데이터에서 직접 mfn_rate를 가져옴
        risk_level = "low" # 기본값
        
        if mfn_rate is not None:
            try:
                mfn_rate_float = float(mfn_rate)
                if mfn_rate_float > 8.0:
                    risk_level = "high"
                elif mfn_rate_float > 3.0:
                    risk_level = "medium"
            except (ValueError, TypeError):
                mfn_rate_float = 0.0 # 오류 시 기본값
        else:
            mfn_rate_float = 0.0

        return {
            "mfn_rate": mfn_rate_float,
            "risk_level": risk_level,
            "answer": result.get("answer", "답변을 생성하지 못했습니다.")
        }

    except Exception as e:
        return {"error": f"p3 실행 중 예외 발생: {str(e)}"}
