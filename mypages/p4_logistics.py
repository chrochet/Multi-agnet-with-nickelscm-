import streamlit as st
import datetime
import time
import pandas as pd

# --- Dynamic Date Generation for Mock Data ---
today = datetime.datetime.now()

# For PO-2024-001 (simulating a recently completed shipment)
# The final status is "Customs cleared and release approved". Let's set its dates in the recent past.
po1_base_date = today - datetime.timedelta(days=10)
po1_eta_date = po1_base_date + datetime.timedelta(days=5)
po1_status_log = [
    ("선적 요청 접수", (po1_base_date + datetime.timedelta(days=0)).strftime("%Y-%m-%d %H:%M")),
    ("선적 출발 (상하이 항)", (po1_base_date + datetime.timedelta(days=2, hours=6)).strftime("%Y-%m-%d %H:%M")),
    ("부산 항 도착 예정", po1_eta_date.strftime("%Y-%m-%d %H:%M")),
    ("부산 항 도착 및 하역", (po1_eta_date + datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")),
    ("보세창고 이동 완료 (A-1 구역)", (po1_eta_date + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")),
    ("통관 서류 제출", (po1_eta_date + datetime.timedelta(days=1, hours=2)).strftime("%Y-%m-%d %H:%M")),
    ("관세/부가세 납부 완료", (po1_eta_date + datetime.timedelta(days=2, hours=5)).strftime("%Y-%m-%d %H:%M")),
    ("통관 완료 및 반출 승인", (po1_eta_date + datetime.timedelta(days=2, hours=7)).strftime("%Y-%m-%d %H:%M")),
]

# For PO-2024-002 (simulating an in-transit shipment)
# The status is "ETA Incheon Port". Let's set its ETA to be in the near future.
po2_base_date = today - datetime.timedelta(days=2)
po2_eta_date = today + datetime.timedelta(days=4)
po2_status_log = [
    ("선적 요청 접수", (po2_base_date + datetime.timedelta(days=0)).strftime("%Y-%m-%d %H:%M")),
    ("선적 출발 (톈진 항)", (po2_base_date + datetime.timedelta(days=1, hours=20)).strftime("%Y-%m-%d %H:%M")),
    ("인천 항 도착 예정", po2_eta_date.strftime("%Y-%m-%d %H:%M")),
]

# --- Mock Data (RAG Knowledge Base) ---
# This simulates a database of shipment information that the RAG agent can query.
MOCK_SHIPMENTS = {
    "PO-2024-001": {
        "supplier": "Valin Group",
        "item": "Nickel Briquettes",
        "quantity": 25000,
        "status_log": po1_status_log,
        "current_status_index": 7, # Final status: "통관 완료 및 반출 승인"
        "eta": po1_eta_date.strftime("%Y-%m-%d %H:%M"),
        "vessel_name": "MSC GULSUN",
        "shipping_docs": ["Bill of Lading #SH12345", "Commercial Invoice #CI67890", "Packing List #PL11223"],
    },
    "PO-2024-002": {
        "supplier": "Jinchuan Group",
        "item": "Nickel Cathodes",
        "quantity": 20000,
        "status_log": po2_status_log,
        "current_status_index": 2, # Current status: "인천 항 도착 예정"
        "eta": po2_eta_date.strftime("%Y-%m-%d %H:%M"),
        "vessel_name": "EVER ACE",
        "shipping_docs": ["Bill of Lading #TJ54321"],
    }
}

# --- RAG Agent Functions ---

def get_shipment_info(po_number, query):
    """
    Simulates a RAG system.
    Retrieves information for a given PO number based on a natural language query.
    """
    shipment = MOCK_SHIPMENTS.get(po_number)
    if not shipment:
        return "해당 발주 번호(PO)를 찾을 수 없습니다."

    query = query.lower()
    
    # Retrieval part
    if "eta" in query or "도착 예정" in query:
        return f"발주번호 {po_number}의 도착 예정일(ETA)은 {shipment['eta']} 입니다."
    elif "상태" in query or "현황" in query or "어디" in query:
        latest_status = shipment["status_log"][shipment["current_status_index"]][0]
        latest_time = shipment["status_log"][shipment["current_status_index"]][1]
        return f"발주번호 {po_number}의 현재 상태는 '{latest_status}'입니다. (업데이트: {latest_time})"
    elif "서류" in query or "document" in query:
        docs = ", ".join(shipment["shipping_docs"])
        return f"발주번호 {po_number} 관련 서류는 다음과 같습니다: {docs}."
    elif "수량" in query or "quantity" in query:
        return f"발주번호 {po_number}의 품목은 {shipment['item']}이며, 수량은 {shipment['quantity'] / 1000:,.2f}t 입니다."
    else:
        # Generation part (fallback)
        return "죄송합니다. 해당 질문에 대한 정보를 찾을 수 없습니다. 'ETA', '상태', '서류', '수량' 등의 키워드로 질문해주세요."

# --- Streamlit Page ---

def page4():
    st.title("4. 운송·물류 관리")
    st.markdown("---")

    # Initialize session state for chat
    if "logistics_messages" not in st.session_state:
        st.session_state.logistics_messages = []

    c1, c2 = st.columns([0.6, 0.4])

    with c1:
        st.subheader("🚚 실시간 운송 현황")
        po_number = st.selectbox("조회할 발주 번호(PO)를 선택하세요.", options=list(MOCK_SHIPMENTS.keys()))

        if po_number:
            shipment = MOCK_SHIPMENTS[po_number]
            current_idx = shipment["current_status_index"]
            
            # --- FIX: logistics_status를 st.session_state에 저장 ---
            try:
                eta_datetime = datetime.datetime.strptime(shipment['eta'], '%Y-%m-%d %H:%M')
                eta_days = (eta_datetime.date() - datetime.date.today()).days
            except (ValueError, TypeError):
                eta_days = -1 # 오류 또는 알 수 없는 경우

            if current_idx >= 4: # 보세창고 도착 이후
                delay_risk = "low"
            elif current_idx >= 1: # 선적 출발 이후
                delay_risk = "medium"
            else: # 선적 요청 접수 단계
                delay_risk = "high"

            logistics_status_data = {
                "po_number": po_number,
                "current_status": shipment["status_log"][current_idx][0],
                "eta_days": eta_days,
                "delay_risk": delay_risk
            }
            st.session_state["logistics_status"] = logistics_status_data
            # --- END FIX ---
            
            with st.container(border=True):
                for i, (status, dt) in enumerate(shipment["status_log"]):
                    if i <= current_idx:
                        st.status(f"**{status}** ({dt})", state="complete", expanded=False)
                    else:
                        st.status(f"**{status}**", state="running", expanded=False)
                
                # Final status and link to P5
                if current_idx >= 7: # 통관 완료
                    st.success("모든 운송/통관 절차가 완료되었습니다. 품질 검사(P5)를 진행할 수 있습니다.")
                    st.info("품질 관리팀에서 성적서(COA)를 업로드하고 품질 검사를 시작할 것입니다.")
                elif current_idx >= 4: # 보세창고 도착
                    st.info("물품이 보세창고에 도착했습니다. 통관 절차를 진행합니다.")

    with c2:
        st.subheader("🤖 물류 AI 에이전트")
        st.markdown("<small>RAG(검색 증강 생성) 기술을 활용하여 물류 데이터를 조회합니다.</small>", unsafe_allow_html=True)
        
        with st.container(height=400, border=True):
            # Display chat messages
            for message in st.session_state.logistics_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Initial greeting
            if not st.session_state.logistics_messages:
                 with st.chat_message("assistant"):
                    st.markdown("안녕하세요! 물류 관련 질문에 답변해 드립니다. 'PO-2024-001 현황 알려줘'와 같이 질문해주세요.")

        # Chat input
        if prompt := st.chat_input("AI 에이전트에게 질문하기..."):
            # Add user message to chat history
            st.session_state.logistics_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Extract PO number from prompt if possible, otherwise use selected
            words = prompt.replace(",", " ").split()
            mentioned_po = next((word.upper() for word in words if word.upper() in MOCK_SHIPMENTS), po_number)

            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("정보를 검색하고 답변을 생성하는 중..."):
                    response = get_shipment_info(mentioned_po, prompt)
                st.markdown(response)
            
            # Add AI response to chat history
            st.session_state.logistics_messages.append({"role": "assistant", "content": response})

# -----------------------------------------------------------
# 🔹 p8_agent가 호출할 실행 전용 함수
# -----------------------------------------------------------
def run_p4_logistics(state: dict) -> dict:
    """p8_agent를 위한 물류 리스크 분석 실행 함수"""
    try:
        # p1_plan에서 PO 번호 가져오기 (없으면 기본값 사용)
        p1_plan = state.get('p1_plan', {})
        po_number = p1_plan.get('po_number', 'PO-2024-001') # 기본 PO 번호

        shipment = MOCK_SHIPMENTS.get(po_number)
        if not shipment:
            return {"error": f"해당 발주 번호({po_number})를 찾을 수 없습니다."}

        current_idx = shipment["current_status_index"]
        
        try:
            eta_datetime = datetime.datetime.strptime(shipment['eta'], '%Y-%m-%d %H:%M')
            eta_days = (eta_datetime.date() - datetime.date.today()).days
        except (ValueError, TypeError):
            eta_days = -1

        if current_idx >= 4:
            delay_risk = "low"
        elif current_idx >= 1:
            delay_risk = "medium"
        else:
            delay_risk = "high"

        return {
            "po_number": po_number,
            "current_status": shipment["status_log"][current_idx][0],
            "eta_days": eta_days,
            "delay_risk": delay_risk
        }
    except Exception as e:
        return {"error": f"p4 실행 중 예외 발생: {str(e)}"}

