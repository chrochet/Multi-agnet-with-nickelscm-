# mypages/purchase_utils.py
import streamlit as st
import pandas as pd
import numpy as np
import joblib
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
from datetime import datetime

# .env 파일에서 환경 변수 로드 (파일이 없어도 에러 없음)
load_dotenv()

# --- 상수 정의 ---
DF_MODEL_PATH = './df_model.pkl'
MODEL_PATH = './final_model.pkl'
FEATURE_COLS_PATH = './feature_cols.pkl'
SCALER_PATH = './scaler.pkl'

# --- 데이터/모델 로딩 함수 (캐싱) ---
@st.cache_data
def load_full_processed_data():
    """모델링에 사용된 전체 데이터를 로드하고 전처리합니다."""
    try:
        df = pd.read_pickle(DF_MODEL_PATH)
        feature_cols = joblib.load(FEATURE_COLS_PATH)
    except FileNotFoundError:
        st.error(f"필수 데이터 파일(df_model.pkl 또는 feature_cols.pkl)을 찾을 수 없습니다.")
        return None, None
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    else:
        st.error("df_model.pkl에 'date' 컬럼이 없어 날짜 기반 조회를 할 수 없습니다.")
        return None, None
    
    df.dropna(subset=['Ni_price'], inplace=True)
    df_filtered = df.dropna(subset=feature_cols).copy()

    if df_filtered.empty:
        st.error("모델 예측에 사용할 수 있는 유효한 데이터가 없습니다.")
        return None, None
    df_filtered = df_filtered.sort_values(by='date').drop_duplicates(subset=['date'], keep='first').set_index('date')
    return df_filtered, feature_cols

@st.cache_resource
def load_model_and_scaler():
    """ML 모델과 스케일러를 로드합니다."""
    try:
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        return model, scaler
    except FileNotFoundError:
        st.error("모델 또는 스케일러 파일(final_model.pkl, scaler.pkl)을 찾을 수 없습니다.")
        return None, None

def get_common_data():
    """
    공통 데이터(데이터, 모델, 스케일러 등)를 로드하고,
    여러 페이지에서 공유할 날짜 선택 UI를 표시합니다.
    """
    df_full, feature_cols = load_full_processed_data()
    model, scaler = load_model_and_scaler()

    if df_full is None or model is None or feature_cols is None or scaler is None:
        st.error("데이터 또는 모델 로딩에 실패하여 페이지를 표시할 수 없습니다.")
        st.stop()

    # st.session_state를 사용하여 여러 페이지에서 날짜를 동기화
    if 'purchase_selected_date' not in st.session_state:
        st.session_state.purchase_selected_date = df_full.index.max().date()
    
    min_date = df_full.index.min().date()
    max_date = df_full.index.max().date()

    # 날짜 입력 위젯
    selected_date = st.date_input(
        "예측 기준 날짜 선택",
        value=st.session_state.purchase_selected_date,
        min_value=min_date,
        max_value=max_date,
        key="shared_date_input" # 고유 키 부여
    )
    # 날짜가 변경되면 session_state에 즉시 반영
    st.session_state.purchase_selected_date = selected_date
    
    # 선택된 날짜를 기준으로 현재 데이터 컨텍스트를 정의
    current_context_data_df = df_full[df_full.index <= pd.to_datetime(selected_date)]
    if current_context_data_df.empty:
        st.error(f"선택하신 {selected_date} 또는 그 이전 날짜에 유효한 데이터가 없습니다. 다른 날짜를 선택해주세요.")
        st.stop()
    current_context_data = current_context_data_df.iloc[-1]
    
    st.markdown(f"**데이터 기준**: `{current_context_data.name.strftime('%Y-%m-%d')}`")
    st.markdown("---")

    return current_context_data, feature_cols, model, scaler

# --- 분석/예측 함수 ---
def predict_price(model, features, data, scaler):
    """주어진 데이터를 사용하여 7일 후 가격을 예측합니다."""
    if data is None: return None
    try:
        input_data = data[features].values.reshape(1, -1)
        scaled_input_data = scaler.transform(input_data)
    except Exception as e:
        st.error(f"데이터 스케일링 중 오류 발생: {e}")
        return None
    prediction = model.predict(scaled_input_data)
    return prediction[0]

# --- UI 컴포넌트 ---
def draw_price_graph(current_price, predicted_price):
    """현재 가격과 예측 가격을 그래프로 시각화합니다."""
    dates = ['현재', '7일 후']
    prices = [current_price, predicted_price]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=prices, mode='lines+markers', name='니켈 가격', line=dict(color='#1f77b4', width=2), marker=dict(size=10)))
    fig.update_layout(
        title="AI 기반 7일 후 가격 예측", xaxis_title="시점", yaxis_title="가격 ($)",
        yaxis_range=[min(prices) * 0.95, max(prices) * 1.05],
        template="plotly_white", margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig, use_container_width=True)

def draw_inventory_graph(current_stock, daily_usage, safety_stock, lead_time, simulation_weeks):
    """재고 변화 예측 그래프를 생성합니다."""
    days_to_plot = simulation_weeks * 7
    days = np.arange(days_to_plot + 1)
    projected_stock = current_stock - (daily_usage * days)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=days, y=projected_stock, mode='lines', name='예상 재고량', line=dict(color='#1f77b4', width=2)))
    fig.add_trace(go.Scatter(x=days, y=[safety_stock] * len(days), mode='lines', name='안전재고', line=dict(color='#d62728', dash='dash', width=2)))
    if lead_time > 0 and lead_time <= days_to_plot:
        fig.add_vline(x=lead_time, line_width=2, line_dash="dot", line_color="#2ca02c", annotation_text="리드타임", annotation_position="top left")

    if daily_usage > 0:
        days_to_safety = (current_stock - safety_stock) / daily_usage
        if 0 <= days_to_safety <= days_to_plot:
            fig.add_scatter(x=[days_to_safety], y=[safety_stock], mode='markers', marker=dict(color='#ff7f0e', size=10, symbol='x'), name='안전재고 도달 예상')

    fig.update_layout(
        title="재고 시뮬레이션", xaxis_title="일(Days)", yaxis_title="재고량 (톤)",
        yaxis_range=[min(0, projected_stock.min() * 1.1) if projected_stock.min() < 0 else 0, current_stock * 1.2],
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        template="plotly_white", margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig, use_container_width=True)
