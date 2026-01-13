import streamlit as st
import sys
from pathlib import Path

# --- 경로 설정: gayoung 폴더의 모듈을 인식하도록 ---
try:
    PROJECT_ROOT = Path(__file__).resolve().parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
except Exception as e:
    st.error(f"초기 경로 설정 중 오류 발생: {e}")

st.set_page_config(page_title="🛡️ SRM & SCM 통합 관리 시스템", layout="wide")

# -----------------------------
# 🔹 페이지 모듈 import
# -----------------------------
from mypages.p1_plan import page1
from mypages.p2_purchase import page2
from mypages.p3_customs import page3
from mypages.p4_logistics import page4
from mypages.p5_quality import page5
from mypages.p6_finance import page6
from mypages.p7_inventory import page7
# page8 대신 p8_agent_main 함수를 임포트합니다.
from mypages.p8_agent import p8_agent_main

# -----------------------------
# 🔹 사이드바 메뉴
# -----------------------------
st.sidebar.title("📦 프로세스 선택")

# 메뉴 이름에서 번호를 제거하여 간결하게 만듭니다.
menu_options = {
    "📝 계획(수요/발주 계획)": "1.",
    "🛒 구매": "2.",
    "📄 수입 통관 준비": "3.",
    "🚚 운송·물류 진행": "4.",
    "✅ 품질 관리": "5.",
    "💰 재무·회계 처리": "6.",
    "🏭 재고 및 생산 투입 관리": "7.",
    "🤖 의사결정 agent": "8."
}

selected_page_title = st.sidebar.radio(
    "업무 단계",
    list(menu_options.keys())
)
menu = menu_options[selected_page_title]


# -----------------------------
# 🔹 선택된 페이지 실행
# -----------------------------
if menu.startswith("1."):
    page1()

elif menu.startswith("2."):
    page2()

elif menu.startswith("3."):
    page3()

elif menu.startswith("4."):
    page4()

elif menu.startswith("5."):
    page5()

elif menu.startswith("6."):
    page6()

elif menu.startswith("7."):
    page7()

# 8번 메뉴 선택 시, 새로운 챗봇 인터페이스를 실행합니다.
elif menu.startswith("8."):
    st.title("8. 🤖 AI 의사결정 에이전트")
    st.caption("p1~p7 페이지들의 데이터를 종합하여 AI가 의사결정을 돕습니다. '재고 분석해줘'와 같이 자연어로 질문하세요.")
    st.markdown("---")

    # 세션 상태에 메시지 기록이 없으면 초기화합니다.
    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = [{"role": "assistant", "content": "안녕하세요! 구매 의사결정에 필요한 분석을 도와드리겠습니다. 무엇을 분석해드릴까요?"}]

    # 이전 대화 내용을 모두 보여줍니다.
    for message in st.session_state.agent_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)
            
    # 사용자로부터 질문을 입력받습니다.
    if prompt := st.chat_input("여기에 질문을 입력하세요..."):
        # 사용자 메시지를 기록하고 보여줍니다.
        st.session_state.agent_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AI 응답을 생성하고 보여줍니다.
        with st.chat_message("assistant"):
            # p8_agent_main 함수는 내부적으로 st.markdown을 사용하여 결과를 출력합니다.
            # 이 함수의 출력을 별도 변수에 저장할 필요 없이 그냥 호출하면 됩니다.
            p8_agent_main(prompt)
            
            # AI의 실제 응답은 p8_agent_main 함수 안에서 st.markdown으로 화면에 그려집니다.
            # 하지만 대화 기록(session_state)에는 저장되지 않는 한계가 있습니다.
            # 현재 구조에서는 사용자 입력만 기록에 남습니다.
            # 이를 개선하려면 p8_agent_main이 응답 문자열을 반환하도록 수정해야 합니다.
            # (현재 요구사항 범위 밖이므로 그대로 둡니다.)