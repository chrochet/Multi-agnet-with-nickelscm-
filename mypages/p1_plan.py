# mypages/p1_plan.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta

def page1():
    st.title("1. 계획(수요/발주 계획)")
    st.caption("주간 기준 재고 소명 및 발주 타이밍을 계산합니다. (7일 = 1주 기준)")
    st.markdown("💡 **예시 값**: 현재 재고 1000, 주간 소요량 350, 안전재고 200, 리드타임 10일, 발주량 500")

    # -----------------------------------------
    # 🔹 입력폼
    # -----------------------------------------
    with st.form("plan_form"):
        col1, col2 = st.columns(2)

        with col1:
            current_stock = st.number_input("현재 재고량", min_value=0.0, step=10.0, value=1000.0)
            weekly_usage = st.number_input("주간 소요량(주당 사용량)", min_value=0.0, step=1.0, value=350.0)
            order_qty = st.number_input("발주량(입고될 수량)", min_value=0.0, step=10.0, value=500.0)

        with col2:
            safety_stock = st.number_input("안전재고", min_value=0.0, step=10.0, value=200.0)
            lead_time = st.number_input("리드타임(입고까지 걸리는 일)", min_value=1, step=1, value=10)
            planning_weeks = st.number_input("시뮬레이션 기간(주)", min_value=4, step=1, value=20)

        submitted = st.form_submit_button("📦 발주 계획 계산하기")

    if not submitted:
        st.info("왼쪽 값을 입력하고 [📦 발주 계획 계산하기] 버튼을 눌러주세요.")
        return

    # st.session_state에 값 저장
    st.session_state['plan_values'] = {
        'current_stock': current_stock,
        'weekly_usage': weekly_usage,
        'safety_stock': safety_stock,
        'lead_time': lead_time,
        'order_qty': order_qty
    }

    # -----------------------------------------
    # 🔹 계산 로직
    # -----------------------------------------
    if weekly_usage <= 0:
        st.warning("주간 소요량이 0보다 커야 재고 소진 계산이 가능합니다.")
        return

    today = date.today()
    daily_usage = weekly_usage / 7   # ← 7일 기준으로 변경됨

    # 재고가 며칠 버티는지
    coverage_days = current_stock / daily_usage
    zero_stock_date = today + timedelta(days=coverage_days)

    # 안전재고 도달 시점
    if current_stock > safety_stock:
        days_until_safety = (current_stock - safety_stock) / daily_usage
        safety_stock_date = today + timedelta(days=days_until_safety)
    else:
        days_until_safety = 0
        safety_stock_date = today

    # 발주 입고 예정일
    incoming_date = today + timedelta(days=lead_time)

    # 권장 발주일 계산
    days_until_order = days_until_safety - lead_time
    if days_until_order <= 0:
        recommended_order_date = today
        order_msg = "⚠️ 안전재고 도달 전 입고가 어려움 → 가능한 한 빨리 발주하세요."
    else:
        recommended_order_date = today + timedelta(days=days_until_order)
        order_msg = f"📌 권장 발주일: **{recommended_order_date}**"

    # -----------------------------------------
    # 🔹 부족재고 계산
    # -----------------------------------------
    total_usage_until_incoming = daily_usage * lead_time
    projected_stock_at_incoming = current_stock - total_usage_until_incoming

    shortage = 0
    if projected_stock_at_incoming < safety_stock:
        shortage = safety_stock - projected_stock_at_incoming

    # -----------------------------------------
    # 🔹 안정성 메시지
    # -----------------------------------------
    if current_stock > safety_stock * 4:
        stability_msg = "🟢 현재 재고는 안전재고의 4배 이상으로 매우 안정적입니다."
    elif current_stock > safety_stock * 2:
        stability_msg = "🟡 재고는 안정적이지만 모니터링이 필요합니다."
    else:
        stability_msg = "🔴 재고가 안전재고에 근접합니다. 발주 주의!"

    # -----------------------------------------
    # 🔹 KPI 표시
    # -----------------------------------------
    colA, colB, colC = st.columns(3)
    colA.metric("재고 커버리지(일)", f"{coverage_days:.1f}")
    colB.metric("안전재고 도달일", safety_stock_date.strftime("%Y-%m-%d"))
    colC.metric("재고 완전 소진 예정일", zero_stock_date.strftime("%Y-%m-%d"))

    st.subheader("📦 발주 계획 요약")
    st.write(order_msg)
    st.write(stability_msg)

    if shortage > 0:
        st.error(f"⚠️ 입고 시점에 **{shortage:.0f} 단위 부족 예상**")
    else:
        st.success("🟢 입고 시점 부족 없음")

    st.write(
        f"""
        - 현재 재고 : **{current_stock:.0f}**
        - 주간 소요량 : **{weekly_usage:.0f}**
        - 안전재고 : **{safety_stock:.0f}**
        - 리드타임 : **{lead_time}일**
        - 발주량(입고량) : **{order_qty:.0f}**
        """
    )

    # -----------------------------------------
    # 🔹 재고 추이 시뮬레이션 (입고 반영)
    # -----------------------------------------
    total_days = planning_weeks * 7
    dates = []
    stocks = []

    stock = current_stock
    for d in range(total_days):
        current_date = today + timedelta(days=d)

        # 매일 재고 감소
        stock -= daily_usage
        if stock < 0:
            stock = 0

        # 입고일 재고 증가
        if current_date == incoming_date:
            stock += order_qty

        dates.append(current_date)
        stocks.append(stock)

    df = pd.DataFrame({"date": dates, "재고량": stocks})

    st.subheader("📉 재고 추이 그래프 (입고 반영)")
    st.line_chart(df.set_index("date"))

    st.caption("※ 모든 계산은 '7일 = 1주' 기준입니다.")
