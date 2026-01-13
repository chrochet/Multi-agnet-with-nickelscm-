# /Users/gwongayoung/캡디 팀플/니켈_캡스톤/gayoung/inventory_manager.py

import os
import math
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st

# --- 1. 환경 설정 및 상수 ---
try:
    # 스크립트 실행 위치를 기준으로 경로 설정
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
    parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
    dotenv_path = os.path.join(parent_dir, '.env')
    load_dotenv(dotenv_path=dotenv_path, override=True)
except Exception:
    script_dir = os.getcwd()

API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=API_KEY) if API_KEY else None

DB_FILE = os.path.join(script_dir, 'inventory_db.csv')
COLUMNS = ['날짜', '구분', '품목', '수량', '내용', 'Lot_No', '잔여수량']
ITEM_NAME = '니켈' # 관리 품목명 고정

# --- 2. 데이터베이스 관리 함수 ---

def load_or_create_inventory_db():
    """
    재고 데이터베이스 파일을 로드하거나 새로 생성합니다.
    파일이 이미 존재하지만 '잔여수량' 컬럼이 없는 경우, 컬럼을 추가하여 호환성을 유지합니다.
    """
    if not os.path.exists(DB_FILE):
        pd.DataFrame(columns=COLUMNS).to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    else:
        df = pd.read_csv(DB_FILE)
        if '잔여수량' not in df.columns:
            df['잔여수량'] = 0
            df.loc[df['구분'] == '입고', '잔여수량'] = df['수량']
            df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

def get_inventory_df():
    """데이터베이스 파일을 읽어 DataFrame으로 반환합니다."""
    load_or_create_inventory_db()
    return pd.read_csv(DB_FILE)

def save_inventory_df(df):
    """데이터프레임을 CSV 파일에 덮어쓰기하여 저장합니다."""
    df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

# --- 3. 핵심 API 함수 ---

def get_real_inventory():
    """
    '잔여수량'의 총합을 계산하여 현재 총 재고량을 반환합니다.
    """
    df = get_inventory_df()
    if df.empty:
        return 0
    return int(df['잔여수량'].sum())

def get_detailed_stock():
    """
    현재 재고를 Lot별 상세 내역(잔여수량 > 0)으로 반환합니다.
    FIFO 순서(날짜 오름차순)로 정렬됩니다.
    """
    df = get_inventory_df()
    detailed_stock = df[(df['구분'] == '입고') & (df['잔여수량'] > 0)].sort_values(by='날짜', ascending=True)
    return detailed_stock

def process_inbound(date, supplier, qty, lot_no):
    """
    품질 합격 시 호출되는 함수. DB에 '입고' 내역을 기록합니다.
    """
    df = get_inventory_df()
    new_record = {
        '날짜': date.strftime('%Y-%m-%d'), '구분': '입고', '품목': ITEM_NAME,
        '수량': qty, '내용': supplier, 'Lot_No': lot_no, '잔여수량': qty
    }
    df_new = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    save_inventory_df(df_new)
    return "입고 완료"

def process_production_input(date, qty_to_use):
    """
    생산 라인 투입 시 호출되는 함수. FIFO에 따라 재고를 차감하고 Lot 추적 정보를 기록합니다.
    """
    current_inventory = get_real_inventory()
    if current_inventory < qty_to_use:
        raise ValueError(f"재고 부족: 현재 재고({current_inventory:,.0f}kg)보다 투입량({qty_to_use:,.0f}kg)이 많습니다.")
    
    df = get_inventory_df()
    available_stock = df[(df['구분'] == '입고') & (df['잔여수량'] > 0)].sort_values(by='날짜', ascending=True)
    
    qty_needed = qty_to_use
    used_lots_info = []
    
    for index, lot in available_stock.iterrows():
        if qty_needed <= 0: break
        amount_to_take = min(lot['잔여수량'], qty_needed)
        df.loc[index, '잔여수량'] -= amount_to_take
        qty_needed -= amount_to_take
        used_lots_info.append(f"{lot['Lot_No']}({amount_to_take:g}kg)")

    used_lots_str = ", ".join(used_lots_info)
    description = f"생산 투입 (사용 Lot: {used_lots_str})"
    
    new_out_record = {
        '날짜': date.strftime('%Y-%m-%d'), '구분': '투입', '품목': ITEM_NAME,
        '수량': -qty_to_use, '내용': description, 'Lot_No': '-', '잔여수량': 0
    }
    df_new = pd.concat([df, pd.DataFrame([new_out_record])], ignore_index=True)
    save_inventory_df(df_new)
    return "투입 완료"

def get_weekly_average_usage():
    """
    최근 7일간의 평균 일일 투입량(소모량)을 계산합니다.
    """
    df = get_inventory_df()
    if df.empty: return 0
    df['날짜'] = pd.to_datetime(df['날짜'])
    seven_days_ago = datetime.now() - pd.Timedelta(days=7)
    recent_inputs = df[(df['구분'] == '투입') & (df['날짜'] >= seven_days_ago)]
    if recent_inputs.empty: return 0
    total_usage = recent_inputs['수량'].sum() * -1
    return total_usage / 7

def get_purchase_recommendation(plan_values: dict = None):
    """
    평균 소모량과 현재고를 바탕으로 발주 필요 여부를 분석하고 제안합니다.
    plan_values가 제공되면 시뮬레이션 값으로, 아니면 DB 값으로 분석합니다.
    """
    # plan_values가 있으면 시뮬레이션 값 사용, 없으면 DB에서 실제 값 조회
    if plan_values and all(k in plan_values for k in ['current_stock', 'weekly_usage', 'safety_stock', 'lead_time']):
        current_inventory = plan_values.get('current_stock', 0)
        weekly_usage = plan_values.get('weekly_usage', 0)
        safety_stock = plan_values.get('safety_stock', 0)
        lead_time = plan_values.get('lead_time', 14)
        avg_daily_usage = weekly_usage / 7 if weekly_usage > 0 else 0
        
        # ROP 계산 = 안전재고 + 리드타임 동안의 사용량
        reorder_point = safety_stock + (avg_daily_usage * lead_time)
    else:
        avg_daily_usage = get_weekly_average_usage()
        current_inventory = get_real_inventory()
        # 원본 로직에서는 safety_stock을 고정값으로 사용했으나, plan_values가 없을 경우 ROP 계산이 어려움
        # 여기서는 DB 기반 분석 시 기본 리드타임과 안전재고 기간을 가정
        LEAD_TIME, SAFETY_STOCK_DAYS = 14, 7
        reorder_point = avg_daily_usage * (LEAD_TIME + SAFETY_STOCK_DAYS)

    is_needed = current_inventory < reorder_point
    shortage_qty = reorder_point - current_inventory
    
    if is_needed:
        recommendation = "발주 요청 권장"
        details = f"현재 재고({current_inventory:,.0f}kg)가 재주문점({reorder_point:,.0f}kg)보다 낮습니다. ({shortage_qty:,.0f}kg 부족)"
    else:
        recommendation = "재고량 충분"
        details = f"현재 재고({current_inventory:,.0f}kg)가 재주문점({reorder_point:,.0f}kg)보다 많습니다."
    
    return {
        "avg_daily_usage": avg_daily_usage, "reorder_point": reorder_point,
        "current_inventory": current_inventory, "is_needed": is_needed,
        "recommendation": recommendation, "details": details,
        "shortage_qty": shortage_qty if is_needed else 0
    }

def generate_purchase_request_email(recommendation_data):
    """
    RAG(검색 증강 생성)를 활용하여 구매팀에 보낼 발주 요청 메일 초안을 생성합니다.
    모든 수량 단위는 톤(t)으로 변환하여 표시합니다.
    """
    if not client:
        return "OpenAI API 키가 설정되지 않아 메일을 생성할 수 없습니다."

    # Convert kg values from recommendation_data to tons for the email content
    current_inventory_t = recommendation_data['current_inventory'] / 1000
    reorder_point_t = recommendation_data['reorder_point'] / 1000
    avg_daily_usage_t = recommendation_data['avg_daily_usage'] / 1000
    shortage_t = recommendation_data['shortage_qty'] / 1000

    # RAG - 1. 검색(Retrieve) 단계: 메일에 필요한 데이터를 톤 단위로 요약/정리합니다.
    context = f"""
    - 품목: {ITEM_NAME}
    - 현재 재고량: {current_inventory_t:,.2f} t
    - 재주문점 (ROP): {reorder_point_t:,.2f} t
    - 최근 7일간 일 평균 소모량: {avg_daily_usage_t:,.3f} t/일
    - 재주문점 대비 부족 수량: {shortage_t:,.2f} t
    """
    
    # Suggest order quantity in tons, rounding up to the nearest 0.1 ton
    suggested_order_qty_t = math.ceil(shortage_t / 0.1) * 0.1 if shortage_t > 0 else 0

    # RAG - 2. 생성(Generate) 단계: 검색된 정보를 바탕으로 LLM에 메일 생성을 요청합니다.
    prompt = f"""
    당신은 제조 기업의 생산관리 담당자입니다. 아래의 재고 분석 데이터를 바탕으로, 구매팀에 보낼 원자재 발주 요청 메일을 공식적이고 정중한 톤으로 작성해주세요.
    모든 단위는 톤(t)으로 작성해야 합니다.

    **재고 분석 데이터 (RAG 컨텍스트):**
    {context}

    **메일 작성 지침:**
    1. 제목: '원자재 긴급 발주 요청 ({ITEM_NAME})' 와 같이 명확하게 작성하세요.
    2. 본문:
        - 발주가 필요한 이유를 재고 데이터에 근거하여 명확히 설명하세요 (현재고가 재주문점 하회).
        - 제안 발주 수량은 {suggested_order_qty_t:,.1f} t 으로 명시하세요.
        - 생산 차질이 발생하지 않도록 신속한 발주 진행을 요청하는 내용을 포함하세요.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert assistant for writing professional business emails in Korean."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI API 호출 중 오류가 발생했습니다: {e}"

def run_p7_inventory(state: dict) -> dict:
    """
    p8_agent를 위한 재고 분석 실행 함수.
    p1에서 입력된 plan_values가 있으면 해당 값으로 시뮬레이션, 없으면 DB기반으로 분석.
    """
    try:
        # p8_agent로부터 plan_values를 전달받아 사용
        plan_values = state.get('p1_plan', {})
        recommendation = get_purchase_recommendation(plan_values)
        
        # p8_agent가 기대하는 'risk_level' 형태로 변환
        risk_level = "warning" if recommendation['is_needed'] else "safe"
        
        return {
            "risk_level": risk_level,
            "details": recommendation['details'],
            "current_inventory": recommendation['current_inventory'],
            "reorder_point": recommendation['reorder_point'],
            "shortage_qty": recommendation['shortage_qty']
        }
    except Exception as e:
        return {"error": f"p7 실행 중 예외 발생: {str(e)}"}

# --- Streamlit Page Function ---
def page7():
    st.title("7. 재고 관리")
    st.caption("현재 니켈 원자재의 재고 현황을 관리하고 생산 투입을 기록합니다.")

    # --- 1. 현재고 및 Lot별 상세 재고 ---
    st.subheader("📊 현재고 현황")
    current_inventory_kg = get_real_inventory()
    st.metric("현재 총 재고량", f"{current_inventory_kg / 1000:,.2f} t")

    st.subheader("📋 Lot별 상세 재고 (FIFO)")
    detailed_stock = get_detailed_stock()
    if not detailed_stock.empty:
        display_df = detailed_stock.copy()
        display_df['수량'] = display_df['수량'] / 1000
        display_df['잔여수량'] = display_df['잔여수량'] / 1000
        display_cols = ['날짜', 'Lot_No', '내용', '수량', '잔여수량']
        cols_to_show = [col for col in display_cols if col in display_df.columns]
        st.dataframe(display_df[cols_to_show].style.format({"수량": "{:,.2f} t", "잔여수량": "{:,.2f} t"}))
    else:
        st.info("현재 입고된 재고가 없습니다.")

    # --- 2. 생산 투입 ---
    st.subheader("🏭 생산 투입 처리")
    with st.form("production_input_form"):
        qty_to_use_tons = st.number_input("투입할 수량 (t)", min_value=0.0, step=0.1, format="%.2f")
        submitted = st.form_submit_button("생산 라인에 투입")

        if submitted:
            if qty_to_use_tons > 0:
                try:
                    result = process_production_input(datetime.now(), qty_to_use_tons * 1000)
                    st.success(f"{qty_to_use_tons:,.2f}t 생산 투입 완료!")
                    st.rerun()
                except ValueError as e:
                    st.error(f"재고 부족: 현재 재고({current_inventory_kg / 1000:,.2f}t)가 투입량({qty_to_use_tons:,.2f}t)보다 많습니다.")
                except Exception as e:
                    st.error(f"처리 중 오류 발생: {e}")
            else:
                st.warning("투입할 수량을 0보다 크게 입력해주세요.")

    # --- 3. 발주 제안 ---
    st.subheader("💡 구매 발주 제안")
    recommendation = get_purchase_recommendation()

    col1, col2, col3 = st.columns(3)
    col1.metric("일 평균 소모량 (7일)", f"{recommendation['avg_daily_usage'] / 1000:,.2f} t")
    col2.metric("재주문점(ROP)", f"{recommendation['reorder_point'] / 1000:,.2f} t")
    col3.metric("현재 재고", f"{recommendation['current_inventory'] / 1000:,.2f} t")

    if recommendation['is_needed']:
        details = f"현재 재고({recommendation['current_inventory'] / 1000:,.2f}t)가 재주문점({recommendation['reorder_point'] / 1000:,.2f}t)보다 낮습니다. ({recommendation['shortage_qty'] / 1000:,.2f}t 부족)"
        st.warning(f"**{recommendation['recommendation']}**: {details}")
        
        if not client:
            st.info("OpenAI API 키가 설정되어야 발주 요청 메일을 생성할 수 있습니다.")
        elif st.button("구매팀에 발주 요청 메일 생성하기"):
            with st.spinner("AI가 메일 초안을 작성 중입니다..."):
                email_draft = generate_purchase_request_email(recommendation)
                st.text_area("메일 초안", email_draft, height=300)
    else:
        details = f"현재 재고({recommendation['current_inventory'] / 1000:,.2f}t)가 재주문점({recommendation['reorder_point'] / 1000:,.2f}t)보다 많습니다."
        st.success(f"**{recommendation['recommendation']}**: {details}")

    st.sidebar.info("이 페이지는 FIFO(선입선출) 원칙에 따라 재고를 관리합니다.")

# --- 초기화 ---
load_or_create_inventory_db()