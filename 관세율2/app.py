import streamlit as st
import pandas as pd
import shutil

# --- 관세율2 모듈 import ---
# 관세율2 폴더명이 "관세율2"가 아니라면 정확한 폴더명을 입력해주세요.
from modules.utils import get_project_root
from modules.data_loader import load_tariff_data
from modules.chroma_builder import build_chroma, get_chroma_client, COLLECTION_NAME
from modules.rag_engine import get_rag_engine



# ============================================================
#              📌 세션 상태 초기값 설정
# ============================================================
def _init_states():
    if "tariff_df" not in st.session_state:
        st.session_state.tariff_df = pd.DataFrame()

    if "rag_engine" not in st.session_state:
        st.session_state.rag_engine = None

    if "db_ready" not in st.session_state:
        st.session_state.db_ready = False


# ============================================================
#                📌 데이터 로딩
# ============================================================
@st.cache_resource
def initialize_data():
    try:
        df = load_tariff_data()
        st.session_state.tariff_df = df
        return df
    except Exception as e:
        st.error(f"데이터 로딩 실패: {e}")
        return pd.DataFrame()


# ============================================================
#                📌 ChromaDB 로딩/구축
# ============================================================
@st.cache_resource
def initialize_chromadb(force_rebuild=False):
    try:
        client = get_chroma_client()
        existing = [c.name for c in client.list_collections()]

        if COLLECTION_NAME not in existing or force_rebuild:
            with st.spinner("📦 ChromaDB 구축 중..."):
                build_chroma(force_rebuild=True)
            st.success("ChromaDB 구축 완료!")

        st.session_state.db_ready = True
        return True

    except Exception as e:
        st.error(f"ChromaDB 초기화 실패: {e}")
        return False


# ============================================================
#                📌 RAG 엔진 준비
# ============================================================
@st.cache_resource
def initialize_rag_engine():
    if st.session_state.db_ready:
        try:
            engine = get_rag_engine()
            st.session_state.rag_engine = engine
            return engine
        except Exception as e:
            st.error(f"RAG 엔진 초기화 실패: {e}")
            return None
    return None


# ============================================================
#                📌 메인 페이지 함수 (내부 UI)
# ============================================================
def page3():
    _init_states()

    st.title("🚢 관세율 조회 & AI 통관 Q&A")
    st.markdown("나라별 금속류 관세율표 조회 및 RAG 기반 통관 상담을 제공합니다.")

    # --------- 데이터 초기화 ---------
    df = initialize_data()

    if not df.empty:
        db_ready = initialize_chromadb()
        if db_ready:
            initialize_rag_engine()

    # ============================================================
    #                   📌 탭 구성
    # ============================================================
    tab1, tab2 = st.tabs(["📑 관세율표 조회", "🤖 AI 통관 Q&A"])


    # ============================================================
    #                📌 탭 1 : 관세율 조회
    # ============================================================
    with tab1:
        st.header("📑 금속류 관세 · HS 코드 조회")

        if st.session_state.tariff_df.empty:
            st.warning("데이터가 없습니다. data 폴더에 CSV를 넣어주세요.")
        else:
            df_display = st.session_state.tariff_df.copy()

            col_left, col_mid, col_right = st.columns([1, 1, 2])

            with col_left:
                countries = ["전체"] + sorted(df_display["country"].unique().tolist())
                selected_country = st.selectbox("국가 선택", countries)

            with col_mid:
                hs_code_query = st.text_input("HS CODE 검색", placeholder="예: 2601")

            with col_right:
                product_query = st.text_input("품목명 검색(desc)", placeholder="예: iron / nickel")

            if selected_country != "전체":
                df_display = df_display[df_display["country"] == selected_country]

            if hs_code_query:
                df_display = df_display[df_display["hs_code"].str.startswith(hs_code_query)]

            if product_query:
                for k in product_query.split():
                    df_display = df_display[df_display["desc"].str.contains(k, case=False)]

            st.markdown("---")
            st.subheader(f"📊 조회 결과: {len(df_display)}건")

            st.dataframe(
                df_display[["country", "hs_code", "desc", "mfn_rate"]],
                height=550,
                width="stretch",
                column_config={
                    "country": "국가",
                    "hs_code": "HS CODE",
                    "desc": "품목명",
                    "mfn_rate": "MFN 관세율",
                }
            )


    # ============================================================
    #            📌 탭 2 : AI RAG 통관 Q&A
    # ============================================================
    with tab2:
        st.header("🤖 AI 통관 Q&A")

        if st.session_state.rag_engine is None:
            st.warning("RAG 엔진이 초기화되지 않았습니다.")
            return

        question = st.text_area(
            "질문을 입력하세요.",
            placeholder="예: 일본 iron ore MFN 세율은?",
            height=100
        )

        if st.button("질문하기", type="primary"):
            if not question.strip():
                st.warning("질문을 입력해주세요.")
            else:
                with st.spinner("AI가 답변 생성 중..."):
                    result = st.session_state.rag_engine.generate_answer(question)
                    st.session_state.last_result = result

        if "last_result" in st.session_state:
            result = st.session_state.last_result

            st.markdown("---")
            answer_col, analysis_col = st.columns([2, 1])

            with answer_col:
                st.subheader("💬 AI 답변")
                st.markdown(result["answer"])

            with analysis_col:
                st.subheader("🧠 질문 분석 결과")
                st.json(result["analysis"])

            st.subheader("📚 참고한 데이터")
            st.dataframe(
                pd.DataFrame(result["sources"]),
                width="stretch",
                column_config={
                    "country": "국가",
                    "hs_code": "HS CODE",
                    "description": "품목명",
                    "mfn_rate": "MFN 관세율",
                }
            )


    # ============================================================
    #                   📌 사이드바 관리 메뉴
    # ============================================================
    with st.sidebar:
        st.header("⚙️ 관리 메뉴")

        if st.button("데이터/DB 새로고침"):
            chroma_path = get_project_root() / "db" / "chroma"

            if chroma_path.exists():
                shutil.rmtree(chroma_path)

            initialize_data.clear()
            initialize_chromadb.clear()
            initialize_rag_engine.clear()

            st.session_state.clear()
            st.rerun()

        st.markdown("---")
        st.markdown("""
        **프로젝트 정보**
        - Version 1.0.0 (METALS 전용)
        - Streamlit + RAG + OpenAI + ChromaDB
        """)

