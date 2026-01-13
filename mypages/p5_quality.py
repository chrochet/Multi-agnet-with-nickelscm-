# mypages/p5_quality.py
import streamlit as st
import datetime
import pandas as pd
import altair as alt
# -----------------------------
# 🔹 모듈 로드
# -----------------------------
# gayoung 폴더의 모듈을 로드 시도. 실패 시 더미 모듈 사용 및 에러 메시지 표시
try:
    from gayoung import quality_manager as qm
    from gayoung import inventory_manager as im
    MODULE_ERROR = False
except ImportError:
    MODULE_ERROR = True

class DummyManager:
    def __init__(self, specs=None):
        self._specs = specs if specs is not None else {}

    def __getattr__(self, name):
        def dummy_func(*args, **kwargs):
            st.error("핵심 기능 모듈(`quality_manager.py` 또는 `inventory_manager.py`)을 로드할 수 없습니다. `gayoung` 폴더에 해당 `.py` 파일이 있는지 확인해주세요.")
            if name == 'extract_data_from_pdf': return None, "모듈을 찾을 수 없습니다."
            if name == 'assess_and_save_quality': return {'status': '오류', 'remark': '모듈 없음'}
            if name == 'get_supplier_risk_and_stage': return {'status': '정보 없음', 'stage': 0, 'action': '모듈 없음'}
            if name == 'process_inbound': return "재고 기록 실패: 모듈 없음"
            if name == 'get_unique_suppliers': return ["(모듈 없음)"]
            if name == 'load_or_create_db': return pd.DataFrame()
            if name == 'generate_action_email': return "메일 생성 실패: 모듈 없음"
            if name == 'generate_inbound_approval_message': return "메시지 생성 실패: 모듈 없음"
            return None
        return dummy_func
    
    @property
    def SPECS(self):
        return self._specs

if MODULE_ERROR:
    qm = DummyManager({
        'ni': {'label': '니켈', 'spec': (99.8, 100)},
        'moisture': {'label': '수분', 'spec': (0, 0.5)},
        'fe': {'label': '철', 'spec': (0, 0.02)},
        's': {'label': '황', 'spec': (0, 0.002)},
        'p': {'label': '인', 'spec': (0, 0.002)},
    })
    im = DummyManager()

# -----------------------------
# 🔹 Helper Functions
# -----------------------------
def to_float(value):
    """Safely convert a value to a float, returning 0.0 for invalid inputs."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

# -----------------------------
# 🔹 DB 초기화
# -----------------------------
if not MODULE_ERROR:
    qm.load_or_create_db()
    im.load_or_create_inventory_db()

# -----------------------------
# 🔹 페이지 실행 함수
# -----------------------------
def page5():
    """
    품질 관리 페이지를 렌더링합니다.
    gayoung/app.py의 품질 관리 파트 코드를 통합했습니다.
    """
    # 페이지에 필요한 세션 상태를 이 곳에서 초기화합니다.
    if 'pdf_data' not in st.session_state: st.session_state.pdf_data = None
    if 'inspection_result' not in st.session_state: st.session_state.inspection_result = None
    if 'srm_status' not in st.session_state: st.session_state.srm_status = None
    if 'history_df' not in st.session_state: st.session_state.history_df = None
    
    st.header("5. 품질 관리")
    
    # 모듈 로드에 실패했으면 에러 메시지를 표시하고 실행을 중단
    if MODULE_ERROR:
        st.error("핵심 기능 모듈(`quality_manager.py` 또는 `inventory_manager.py`)을 로드할 수 없습니다. `gayoung` 폴더에 해당 `.py` 파일이 있는지 확인해주세요.")
        st.warning("현재 일부 기능이 제한됩니다. 코드 관리자에게 문의하세요.")
        return

    tab_choice = st.radio(
        "작업 선택", ["📝 신규 품질 검사", "📊 이력 조회 및 분석"],
        horizontal=True, key="quality_tab_choice", label_visibility="collapsed"
    )

    if tab_choice == "📝 신규 품질 검사":
        st.subheader("1. 공급사 성적서(COA) 자동 분석")
        uploaded_file = st.file_uploader("PDF 형식의 성적서를 업로드하세요.", type="pdf", key="quality_uploader")
        if uploaded_file:
            with st.spinner("PDF를 읽고 AI가 데이터를 추출하는 중입니다..."):
                data, msg = qm.extract_data_from_pdf(uploaded_file)
                if data:
                    st.session_state.pdf_data = data
                    st.success(f"데이터 추출 성공! (공급사: {data.get('supplier')}, Lot: {data.get('lot_no')})")
                    st.rerun()
                else:
                    st.error(f"추출 실패: {msg}")

        st.subheader("2. 품질 데이터 검증")
        pdf_data = st.session_state.get('pdf_data') or {}
        with st.form("inspection_form"):
            c1, c2, c3 = st.columns(3)
            supplier = c1.text_input("공급사명", value=pdf_data.get('supplier', ''))
            lot_no = c2.text_input("Lot No.", value=pdf_data.get('lot_no', ''))
            quantity = c3.number_input("입고 수량 (kg)", value=to_float(pdf_data.get('quantity')), format="%.2f")
            date = st.date_input("검사 날짜", datetime.date.today())
            st.divider()
            st.markdown("**품질 항목별 수치 입력 (COA vs 실측)**")
            
            items_to_display = ['ni', 'moisture', 'fe', 's', 'p']
            columns = st.columns(len(items_to_display))
            coa_values, actual_values = {}, {}
            for col, item in zip(columns, items_to_display):
                with col:
                    if item in qm.SPECS:
                        st.info(f"{qm.SPECS[item]['label']} ({item.upper()})")
                        coa_value = to_float(pdf_data.get(item))
                        coa_values[item] = col.number_input("COA", value=coa_value, key=f"coa_{item}", format="%.4f")
                        actual_values[item] = col.number_input("실측", value=coa_value, key=f"actual_{item}", format="%.4f")
            
            submitted = st.form_submit_button("검사 실행", type="primary", use_container_width=True)

        if submitted:
            if not supplier or not lot_no:
                st.warning("공급사명과 Lot No.를 입력해야 합니다.")
            else:
                with st.spinner("품질 기준 평가 및 SRM 분석 중..."):
                    result = qm.assess_and_save_quality(date, supplier, lot_no, quantity, coa_values, actual_values)
                    st.session_state.inspection_result = result
                    st.session_state.last_inputs = {'date': date, 'supplier': supplier, 'lot_no': lot_no, 'quantity': quantity, 'remark': result.get('remark')}
                    srm_status = qm.get_supplier_risk_and_stage(supplier)
                    st.session_state.srm_status = srm_status

                    # --- FIX: quality_status를 st.session_state에 저장 ---
                    quality_status_data = {
                        "inspection_result": "pass" if result['status'] == "합격" else "fail",
                        "risk_reason": result.get('remark', 'N/A'),
                        "lot_no": lot_no,
                        "supplier": supplier,
                        "quantity": quantity,
                        "date": date.strftime('%Y-%m-%d')
                    }
                    st.session_state["quality_status"] = quality_status_data
                    # --- END FIX ---
                    
                    st.rerun()

        if 'inspection_result' in st.session_state and st.session_state.inspection_result:
            result = st.session_state.inspection_result
            srm = st.session_state.srm_status
            inputs = st.session_state.last_inputs
            
            st.subheader("3. 판정 결과 및 조치")
            if result['status'] == "합격":
                st.success(f"**판정: {result['status']}** ({inputs['remark']})")
                st.metric(label=f"'{inputs['supplier']}' SRM 등급", value=srm['status'])
                with st.spinner("재고 관리 시스템에 입고 기록 중..."):
                    inbound_msg = im.process_inbound(inputs['date'], inputs['supplier'], inputs['quantity'], inputs['lot_no'])
                    st.success(f"✅ {inbound_msg}: Lot No '{inputs['lot_no']}'({inputs['quantity']}kg)가 재고에 추가되었습니다.")
            else:
                st.error(f"**판정: {result['status']}** (사유: {inputs['remark']})")
                st.warning(f"**SRM 단계: {srm['stage']}단계 - {srm['status']}**")
                st.info(f"**권고 조치:** {srm['action']}")
                if srm.get('stage', 0) > 0:
                    with st.spinner("AI가 조치 이메일 초안을 생성 중입니다..."):
                        email_draft = qm.generate_action_email(inputs['supplier'], inputs['lot_no'], srm['stage'], inputs['remark'])
                        with st.expander("✍️ AI 추천 이메일 초안 보기"):
                            st.text_area("이메일 내용", email_draft, height=300)
                            st.button("복사하기", key=f"copy_{inputs['lot_no']}")

            st.divider()
            st.subheader("🚚 물류팀 알림")
            inbound_message = qm.generate_inbound_approval_message(inputs['supplier'], inputs['lot_no'], result)
            if "⛔" in inbound_message: st.warning(inbound_message)
            else: st.info(f"📦 AI 생성 입고 승인 메시지:\n{inbound_message}")
            del st.session_state.inspection_result, st.session_state.srm_status, st.session_state.last_inputs

    elif tab_choice == "📊 이력 조회 및 분석":
        st.subheader("검사 이력 조회 및 분석")
        with st.form("history_filter_form"):
            c1, c2 = st.columns([1, 1])
            today = datetime.date.today()
            start_date = c1.date_input("시작일", today - datetime.timedelta(days=30))
            end_date = c2.date_input("종료일", today)
            suppliers = ["전체"] + qm.get_unique_suppliers()
            selected_supplier = st.selectbox("공급사 선택", suppliers)
            search_clicked = st.form_submit_button("조회하기", type="primary", use_container_width=True)

        if search_clicked:
            df = qm.load_or_create_db()
            df['날짜'] = pd.to_datetime(df['날짜']).dt.date
            mask = (df['날짜'] >= start_date) & (df['날짜'] <= end_date)
            if selected_supplier != "전체":
                mask &= (df['공급사명'] == selected_supplier)
            filtered_df = df[mask]
            if filtered_df.empty:
                st.session_state.history_df = None
                st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
            else:
                st.session_state.history_df = filtered_df
        
        if st.session_state.history_df is not None:
            filtered_df = st.session_state.history_df
            st.success(f"총 {len(filtered_df)}건의 검사 이력이 조회되었습니다.")
            pass_count = filtered_df[filtered_df['판정'] == '합격'].shape[0]
            fail_count = filtered_df[filtered_df['판정'] == '불합격'].shape[0]
            m1, m2 = st.columns(2)
            m1.metric("✅ 합격 건수", f"{pass_count} 건")
            m2.metric("❌ 불합격 건수", f"{fail_count} 건")
            
            st.markdown("**조회된 데이터 (행을 클릭하여 상세 정보 확인)**")
            display_cols = ['날짜', '공급사명', 'Lot No', '판정', '비고', '수량', 'actual_ni', 'actual_moisture', 'actual_fe', 'actual_s', 'actual_p']
            existing_display_cols = [col for col in display_cols if col in filtered_df.columns]
            df_display = filtered_df[existing_display_cols].copy()
            rename_map = {
                '공급사명': '공급사', 'Lot No': 'Lot', '비고': '사유', '수량': '수량(kg)',
                'actual_ni': 'Ni(%)', 'actual_moisture': '수분(%)', 'actual_fe': 'Fe(%)',
                'actual_s': 'S(%)', 'actual_p': 'P(%)'
            }
            df_display.rename(columns={k: v for k, v in rename_map.items() if k in df_display.columns}, inplace=True)
            event = st.dataframe(df_display, key="history_table", on_select="rerun", selection_mode="single-row", width='stretch')

            if event.selection.rows:
                selected_index = event.selection.rows[0]
                original_index = df_display.index[selected_index]
                selected_row = filtered_df.loc[original_index]
                with st.expander(f"🔍 상세 정보 (Lot: {selected_row['Lot No']})", expanded=True):
                    items = ['ni', 'moisture', 'fe', 's', 'p']
                    details_data = {
                        "품질 항목": [qm.SPECS.get(item, {}).get('label', item.upper()) for item in items],
                        "COA 값": [selected_row.get(f'coa_{item}') for item in items],
                        "실측 값": [selected_row.get(f'actual_{item}') for item in items]
                    }
                    details_df = pd.DataFrame(details_data)
                    try:
                        details_df['차이 (실측-COA)'] = pd.to_numeric(details_df['실측 값'], errors='coerce') - pd.to_numeric(details_df['COA 값'], errors='coerce')
                    except (TypeError, ValueError):
                        details_df['차이 (실측-COA)'] = None
                    def highlight_diff(val):
                        if pd.isna(val): return ''
                        return f'color: {"red" if val > 0.0001 else "green" if val < -0.0001 else "gray"}'
                    st.dataframe(details_df.style.applymap(highlight_diff, subset=['차이 (실측-COA)']).format({'COA 값': '{:.4f}', '실측 값': '{:.4f}', '차이 (실측-COA)': '{:+.4f}'}), width='stretch')

            st.subheader("주요 항목 변화 추이")
            st.info("💡 그래프는 마우스 휠로 확대/축소하고, 드래그하여 이동할 수 있습니다.")
            base = alt.Chart(filtered_df).encode(alt.X('날짜:T', axis=alt.Axis(title='날짜', format='%Y-%m-%d')))
            quality_base = base.transform_fold(['actual_ni', 'actual_moisture', 'actual_fe', 'actual_s', 'actual_p'], as_=['key', 'value'])
            quality_lines = quality_base.mark_line(opacity=0.5).encode(alt.Y('value:Q', title='품질 수치', scale=alt.Scale(zero=False)), color=alt.Color('key:N', title='품질 항목'))
            quality_points = quality_base.mark_point(size=80, filled=True, stroke='white', strokeWidth=1).encode(alt.Y('value:Q'), color=alt.Color('판정:N', title="판정 결과", scale=alt.Scale(domain=['합격', '불합격'], range=['#2ca02c', '#d62728'])), tooltip=[alt.Tooltip('날짜:T', title='날짜', format='%Y-%m-%d'), alt.Tooltip('공급사명:N', title='공급사'), alt.Tooltip('Lot No:N', title='Lot No.'), alt.Tooltip('key:N', title='품질 항목'), alt.Tooltip('value:Q', title='측정치', format='.4f'), alt.Tooltip('판정:N', title='판정')])
            quantity_bars = base.mark_bar(size=10, opacity=0.3).encode(alt.Y('수량:Q', axis=alt.Axis(title='수량 (kg)', titleColor='#5276A7')), tooltip=[alt.Tooltip('날짜:T', title='날짜', format='%Y-%m-%d'), alt.Tooltip('수량:Q', title='수량 (kg)')])
            final_chart = alt.layer(quantity_bars, quality_lines, quality_points).resolve_scale(y='independent').interactive()
            st.altair_chart(final_chart, use_container_width=True)

# -----------------------------------------------------------
# 🔹 p8_agent가 호출할 실행 전용 함수
# -----------------------------------------------------------
def run_p5_quality(state: dict) -> dict:
    """p8_agent를 위한 공급사 품질 리스크 분석 실행 함수"""
    try:
        if MODULE_ERROR:
            return {"error": "quality_manager 모듈을 로드할 수 없습니다."}

        # p1_plan에서 공급사 이름 가져오기
        p1_plan = state.get('p1_plan', {})
        supplier = p1_plan.get('supplier', None)
        
        # 공급사 정보가 없으면 오류 대신 분석 스킵 메시지 반환
        if not supplier:
            return {
                "status": "skipped",
                "error": "분석할 공급사 정보가 지정되지 않았습니다."
            }

        # DB 초기화 및 리스크 분석
        qm.load_or_create_db()
        srm_status = qm.get_supplier_risk_and_stage(supplier)

        return {
            "supplier": supplier,
            "status": srm_status.get('status'),
            "stage": srm_status.get('stage'),
            "action": srm_status.get('action')
        }
    except Exception as e:
        return {"error": f"p5 실행 중 예외 발생: {str(e)}"}