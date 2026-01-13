# mypages/p6_finance.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from . import purchase_utils as pu

def page6():
    """'재무·회계 처리' 페이지를 렌더링합니다."""
    st.header("6. 재무·회계 처리")

    # 공통 유틸리티 함수를 호출하여 데이터 로드 및 날짜 선택 UI 표시
    current_context_data, _, _, _ = pu.get_common_data()
    
    # '구매' 페이지에서 전달된 세션 상태 값 확인
    order_quantity = st.session_state.get('order_quantity', 0)
    predicted_price = st.session_state.get('predicted_price', 0)
    
    if order_quantity == 0 or predicted_price == 0:
        st.warning("먼저 '2. 구매' 페이지의 사이드바에서 시뮬레이션 정보를 입력하고, 가격 예측을 수행해야 합니다.")
        st.info("좌측 메뉴에서 '2. 구매'를 선택하여 진행해주세요.")
        st.stop()

    # --- 데이터 기반 가상 공급업체 생성 로직 ---
    lme_linked_price = predicted_price * 1.01
    china_pmi = current_context_data.get("CN_PMI_index", 50)
    china_spot_price = predicted_price * (1 + (china_pmi - 50) / 100 * 0.02)
    long_term_contract_price = current_context_data.get("ma_30", predicted_price)
    
    unit_prices = [lme_linked_price, china_spot_price, long_term_contract_price]
    supplier_names = ["LME 연동", "중국 현물", "장기 계약"]

    np.random.seed(0) # 결과를 일정하게 유지
    suppliers_data = []
    for name, price in zip(supplier_names, unit_prices):
        lead_time_supplier = np.random.randint(7, 20)
        payment_condition = np.random.choice(["선결제", "30일 후", "60일 후"])
        suppliers_data.append([name, price, lead_time_supplier, payment_condition])
    
    suppliers_df = pd.DataFrame(suppliers_data, columns=["공급사", "단가 ($)", "리드타임 (일)", "결제조건"])
    
    # --- 공급사 추천 점수 계산 ---
    scores = []
    price_min, price_max = suppliers_df["단가 ($)"].min(), suppliers_df["단가 ($)"].max()
    lead_time_min, lead_time_max = suppliers_df["리드타임 (일)"].min(), suppliers_df["리드타임 (일)"].max()

    for _, row in suppliers_df.iterrows():
        price_score = (price_max - row["단가 ($)"]) / (price_max - price_min + 1e-6) if price_max > price_min else 0.5
        lead_time_score = (lead_time_max - row["리드타임 (일)"]) / (lead_time_max - lead_time_min + 1e-6) if lead_time_max > lead_time_min else 0.5
        payment_score = {"60일 후": 1, "30일 후": 0.5, "선결제": 0}[row["결제조건"]]
        total_score = price_score * 0.5 + lead_time_score * 0.3 + payment_score * 0.2
        scores.append(total_score)
    
    suppliers_df["추천 점수"] = scores
    best_supplier = suppliers_df.loc[suppliers_df["추천 점수"].idxmax()]
    selected_price = best_supplier["단가 ($)"]
    total_purchase_cost = selected_price * order_quantity

    # --- UI Layout ---
    with st.container(border=True):
        st.info(f"**발주 수량**: `{order_quantity}` 톤  |  **기준 단가 (AI 예측)**: `${predicted_price:,.2f}`/톤")
    st.markdown("---")

    # --- 1. 공급업체 비교 및 선택 ---
    st.subheader("1. 공급업체 비교 및 선택")
    with st.container(border=True):
        st.dataframe(suppliers_df.style.format({"단가 ($)": "${:,.2f}", "추천 점수": "{:.2f}"}).hide(axis="index"), use_container_width=True)
        st.success(f"**AI 추천 공급사**: **{best_supplier['공급사']}** (사유: 가격, 리드타임, 결제조건을 종합한 추천 점수 최우수)")
    st.markdown("---")

    # --- 2. 총 구매 원가 상세 계산 ---
    st.subheader("2. 총 구매 원가 상세 계산")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("###### 비용 입력")
            tariff_rate = st.number_input("관세율 (%)", min_value=0.0, value=3.5, step=0.1, key="p6_tariff")
            vat_rate = st.number_input("부가세율 (%)", min_value=0.0, value=10.0, step=0.1, key="p6_vat")
            exchange_rate = st.number_input("원/달러 환율", min_value=1000.0, value=1350.0, step=1.0, key="p6_exchange")
        
        cost_krw = total_purchase_cost * exchange_rate
        tariff_cost_krw = cost_krw * (tariff_rate / 100)
        vat_cost_krw = (cost_krw + tariff_cost_krw) * (vat_rate / 100)
        final_cost_krw = cost_krw + tariff_cost_krw

        with col2:
            st.markdown("###### 최종 원가 (KRW)")
            st.metric("자재비 (원화)", f"₩ {cost_krw:,.0f}")
            st.metric("관세 (원화)", f"₩ {tariff_cost_krw:,.0f}")
            st.metric("부가세 (원화)", f"₩ {vat_cost_krw:,.0f}")
            st.metric("최종 구매 원가 (부가세 제외)", f"₩ {final_cost_krw:,.0f}", help="원가 = 자재비 + 관세")
    st.markdown("---")

    # --- FIX: finance_summary를 st.session_state에 저장 ---
    finance_summary_data = {
        "total_cost": final_cost_krw,
        "unit_cost": final_cost_krw / order_quantity if order_quantity > 0 else 0, # 0으로 나누기 방지
        "total_purchase_cost_usd": total_purchase_cost,
        "selected_unit_price_usd": selected_price,
        "tariff_rate": tariff_rate,
        "vat_rate": vat_rate,
        "exchange_rate": exchange_rate
    }
    st.session_state["finance_summary"] = finance_summary_data
    # --- END FIX ---

    # --- 3. 회계 전표 및 인보이스 ---
    st.subheader("3. 회계 처리 (초안)")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("회계 전표")
            journal_entry = {
                "계정과목": ["원재료", "미지급금", "부가세대급금"],
                "차변(Dr.)": [f"{final_cost_krw:,.0f}", "", f"{vat_cost_krw:,.0f}"],
                "대변(Cr.)": ["", f"{final_cost_krw + vat_cost_krw:,.0f}", ""],
            }
            st.dataframe(pd.DataFrame(journal_entry).style.hide(axis="index"), use_container_width=True)

    with col2:
        with st.container(border=True):
            st.subheader("인보이스(송장)")
            invoice_template = f'''**INVOICE**
---
**To:** Our Company Inc.
**From:** {best_supplier['공급사']}
**Date:** {datetime.now().strftime('%Y-%m-%d')}
---
**Description:** Nickel Cathode
**Quantity:** {order_quantity} a.i. ton
**Unit Price:** ${selected_price:,.2f}
---
**Total Amount:** ${total_purchase_cost:,.2f}
            '''
            st.text_area("인보이스 내용", value=invoice_template, height=255)

# -----------------------------------------------------------
# 🔹 p8_agent가 호출할 실행 전용 함수
# -----------------------------------------------------------
def run_p6_finance(state: dict) -> dict:
    """p8_agent를 위한 재무 분석 실행 함수"""
    try:
        # 1. 의존성 데이터 가져오기 (p8_agent의 state 구조에 맞게 수정)
        p1_plan = state.get('p1_plan', {})
        agent_outputs = state.get('agent_outputs', {})
        p2_output = agent_outputs.get('p2', {}) 
        p3_output = agent_outputs.get('p3', {})

        order_quantity = p1_plan.get('order_qty')
        predicted_price = p2_output.get('predicted_price')

        if order_quantity is None:
            return {"error": "p1(발주량) 정보가 필요합니다. 에이전트 페이지 상단의 입력 폼에 값을 입력해주세요."}
        if predicted_price is None:
            return {"error": "p2(예측가격) 데이터가 필요합니다. 가격 예측 에이전트가 먼저 실행되어야 합니다."}

        # 2. page6의 핵심 로직 재현
        # purchase_utils를 직접 호출하기보다, state에 필요한 값이 모두 전달되었다고 가정
        # 만약 current_context_data가 필요하다면 p8에서 미리 로드하여 state에 넣어주는 것이 더 좋음
        # 여기서는 p2 예측가격을 중심으로 단순화
        lme_linked_price = predicted_price * 1.01
        # cn_pmi, ma_30 등 추가 정보가 필요하다면 p8에서 다른 에이전트를 통해 state에 추가해야 함
        china_spot_price = predicted_price * (1 + (50 - 50) / 100 * 0.02) # 예시 PMI: 50
        long_term_contract_price = predicted_price # 예시 ma_30
    
        unit_prices = [lme_linked_price, china_spot_price, long_term_contract_price]
        supplier_names = ["LME 연동", "중국 현물", "장기 계약"]

        np.random.seed(0)
        suppliers_data = []
        for name, price in zip(supplier_names, unit_prices):
            suppliers_data.append([name, price, np.random.randint(7, 20), np.random.choice(["선결제", "30일 후", "60일 후"])])
    
        suppliers_df = pd.DataFrame(suppliers_data, columns=["공급사", "단가 ($)", "리드타임 (일)", "결제조건"])
    
        scores = []
        price_min, price_max = suppliers_df["단가 ($)"].min(), suppliers_df["단가 ($)"].max()
        lead_time_min, lead_time_max = suppliers_df["리드타임 (일)"].min(), suppliers_df["리드타임 (일)"].max()

        for _, row in suppliers_df.iterrows():
            price_score = (price_max - row["단가 ($)"]) / (price_max - price_min + 1e-6) if price_max > price_min else 0.5
            lead_time_score = (lead_time_max - row["리드타임 (일)"]) / (lead_time_max - lead_time_min + 1e-6) if lead_time_max > lead_time_min else 0.5
            payment_score = {"60일 후": 1, "30일 후": 0.5, "선결제": 0}[row["결제조건"]]
            total_score = price_score * 0.5 + lead_time_score * 0.3 + payment_score * 0.2
            scores.append(total_score)
    
        suppliers_df["추천 점수"] = scores
        best_supplier = suppliers_df.loc[suppliers_df["추천 점수"].idxmax()]
        selected_price = best_supplier["단가 ($)"]
        total_purchase_cost = selected_price * order_quantity

        # 3. 비용 계산 (UI 입력 대신 기본값/의존성 데이터 사용)
        tariff_rate = p3_output.get('mfn_rate', 3.5) if p3_output else 3.5 # p3 결과가 있으면 사용, 없으면 3.5%
        vat_rate = 10.0
        exchange_rate = 1350.0
        
        cost_krw = total_purchase_cost * exchange_rate
        tariff_cost_krw = cost_krw * (tariff_rate / 100)
        final_cost_krw = cost_krw + tariff_cost_krw

        # 4. 결과 반환
        return {
            "total_cost": final_cost_krw,
            "unit_cost": final_cost_krw / order_quantity if order_quantity > 0 else 0,
            "best_supplier": best_supplier['공급사'],
            "selected_price_usd": selected_price,
            "tariff_rate": tariff_rate,
            "exchange_rate": exchange_rate
        }

    except Exception as e:
        import traceback
        return {"error": f"p6 실행 중 예외 발생: {str(e)}", "trace": traceback.format_exc()}