# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import joblib
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re
from streamlit_chat import message
import shap
import openai
from googleapiclient.discovery import build
import time
import requests
from bs4 import BeautifulSoup

# --- Path and Environment settings ---
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path, override=True)
except (NameError, FileNotFoundError):
    project_root = os.getcwd()

# --- Path settings ---
DF_MODEL_PATH = os.path.join(project_root, 'df_model.pkl')
MODEL_PATH = os.path.join(project_root, 'final_model.pkl')
FEATURE_COLS_PATH = os.path.join(project_root, 'feature_cols.pkl')
SCALER_PATH = os.path.join(project_root, 'scaler.pkl')

# --- Load environment variables ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Constants ---
KEYWORD_MAP = {
    'Ni_price': '니켈 가격', 'Cu_price': '구리 가격', 'Al_price': '알루미늄 가격', 'Gold_price': '금 가격',
    'Dubai_Oil_price': '두바이유', 'Dollar_index': '달러 인덱스', 'NASDAQ_index': '나스닥 지수',
    'US_PMI_index': '미국 PMI', 'CN_PMI_index': '중국 PMI', 'TR_US_10Y_GB_index': '미국 10년물 국채 금리',
    'US_CPI_index': '미국 CPI', 'US_PPI_index': '미국 PPI', 'VIX_price': 'VIX 지수'
}

# --- Data/Model Loading Functions (with Caching) ---
@st.cache_data
def load_full_processed_data():
    try:
        df = pd.read_pickle(DF_MODEL_PATH)
        feature_cols = joblib.load(FEATURE_COLS_PATH)
    except FileNotFoundError: return None, None
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df.dropna(subset=['Ni_price'], inplace=True)
    df_filtered = df.dropna(subset=feature_cols).copy()
    if df_filtered.empty: return None, None
    df_filtered = df_filtered.sort_values(by='date').drop_duplicates(subset=['date'], keep='first').set_index('date')
    return df_filtered, feature_cols

@st.cache_resource
def load_model_and_scaler():
    try:
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        return model, scaler
    except FileNotFoundError: return None, None

@st.cache_resource
def load_shap_explainer(_model, _scaler, background_data):
    if _model is None or background_data is None or _scaler is None: return None
    def predict_fn(X):
        X_df = pd.DataFrame(X, columns=background_data.columns)
        X_scaled = _scaler.transform(X_df)
        return _model.predict(X_scaled)
    background_summary = shap.sample(background_data, 50) 
    return shap.KernelExplainer(predict_fn, background_summary)

# --- Analysis/Prediction/Search Functions ---
def predict_price(model, features, data, scaler):
    if any(v is None for v in [model, features, data, scaler]): return None
    input_data = data[features].values.reshape(1, -1)
    scaled_input_data = scaler.transform(input_data)
    return model.predict(scaled_input_data)[0]

def get_top_shap_features(explainer, input_data, feature_names, top_n=3):
    if explainer is None: return {"error": "SHAP explainer not loaded."}
    try:
        shap_values = explainer.shap_values(input_data, nsamples=50)
        if isinstance(shap_values, list): shap_values = shap_values[0]
        if len(shap_values.shape) > 1: shap_values = shap_values[0]
        feature_importance = pd.DataFrame(list(zip(feature_names, np.abs(shap_values))), columns=['feature', 'importance'])
        if feature_importance['importance'].isnull().all(): return []
        feature_importance = feature_importance.sort_values(by='importance', ascending=False)
        return feature_importance.head(top_n)['feature'].tolist()
    except Exception as e: return {"error": f"SHAP 분석 오류: {e}"}

def search_google_news(query, start_date, end_date, num=5):
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return {"error": "Google API 키 또는 CSE ID가 설정되지 않았습니다."}
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        sort_by_date = f"date:r:{start_date.strftime('%Y%m%d')}:{end_date.strftime('%Y%m%d')}"
        res = service.cse().list(q=query, cx=GOOGLE_CSE_ID, num=num, sort=sort_by_date, lr='lang_ko').execute()
        return res.get('items', [])
    except Exception as e: return {"error": f"뉴스 검색 중 오류 발생: {e}"}

def perform_price_analysis(current_context_data, explainer, feature_cols, selected_date):
    """
    Analyzes price fluctuation causes using SHAP and Google News.
    Returns a dictionary with structured data, not a formatted string.
    """
    prefix_desc = {"lag": "니켈 가격 자체 동향", "ma": "기술적 분석", "PC_COM": "원자재 시장", "PMI": "제조업 경기", "CPI": "인플레이션", "ret": "투자 심리", "GB": "미국 국채 금리"}

    # 1. SHAP Analysis
    input_data_df = pd.DataFrame([current_context_data[feature_cols].values], columns=feature_cols)
    top_features = get_top_shap_features(explainer, input_data_df, feature_cols, top_n=3)
    if isinstance(top_features, dict) and 'error' in top_features:
        return top_features

    # 2. Smart Keyword Generation
    PREFIX_KEYWORD_MAP = {'lag': ['니켈 가격'], 'ma': ['기술적 분석'], 'ret': ['니켈 변동성'], 'PC_fin': ['금융 시장'], 'PC_COM': ['원자재', '비철금속', 'LME'], 'PMI': ['PMI', '제조업'], 'CPI': ['CPI', '물가'], 'PPI': ['PPI'], 'GB': ['국채 금리'], 'VIX': ['VIX 지수'], 'Dollar': ['달러 인덱스'], 'NASDAQ': ['나스닥'], 'Gold': ['금 가격'], 'Cu': ['구리 가격'], 'Al': ['알루미늄 가격'], 'Dubai_Oil': ['유가']}
    shap_keywords = []
    for feature in top_features:
        found_prefix = False
        for prefix, keywords in PREFIX_KEYWORD_MAP.items():
            if feature.startswith(prefix):
                shap_keywords.extend(keywords)
                found_prefix = True; break
        if not found_prefix and KEYWORD_MAP.get(feature):
            shap_keywords.append(KEYWORD_MAP.get(feature))
    if not shap_keywords: shap_keywords.append('니켈 가격')
    shap_keywords = list(set(filter(None, shap_keywords)))

    # 3. News Search
    search_query = "니켈" + (" (" + " OR ".join(shap_keywords) + ")" if shap_keywords else "")
    end_date = pd.to_datetime(selected_date)
    start_date = end_date - timedelta(days=14)
    news_items = search_google_news(search_query, start_date, end_date)
    if isinstance(news_items, dict) and 'error' in news_items:
        return news_items

    # 4. Score and Sort News
    reranked_news = []
    if news_items:
        for item in news_items:
            search_text = f"{item.get('title', '')} {item.get('snippet', '')}"
            score = sum(1 for keyword in shap_keywords if keyword in search_text)
            if score > 0:
                reranked_news.append({
                    "title": item.get('title'),
                    "link": item.get('link'),
                    "snippet": item.get('snippet', '요약 정보 없음').strip(),
                    "relevance_score": score
                })
        reranked_news.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

    # 5. Generate Final Structured Data
    main_factors_list = list(set([prefix_desc.get(f.split('_')[0], "시장 동향") for f in top_features]))
    main_factors = " 및 ".join(main_factors_list) if main_factors_list else "전반적인 시장 동향"

    return {
        "main_factors_str": f"주요 가격 변동 요인은 **{main_factors}**(으)로 보입니다.",
        "top_features": top_features,
        "relevant_news": reranked_news[:3] # Return top 3 news
    }

def summarize_url_content(url):
    """Fetches content from a URL and summarizes it using OpenAI."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ko;q=0.8'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Heuristics to find main content, trying common tags for articles
        main_content = soup.find('article') or soup.find('main') or soup.find("div", class_=re.compile("post|article|content"))
        
        if main_content:
            paragraphs = main_content.find_all('p')
        else:
            # As a fallback, get all paragraphs from the body
            paragraphs = soup.body.find_all('p') if soup.body else []

        text_content = ' '.join([p.get_text(strip=True) for p in paragraphs])

        if not text_content.strip():
            # If no paragraphs, try to get all text from body and clean it up
            if soup.body:
                text_content = ' '.join(soup.body.get_text(separator=' ', strip=True).split())
            if not text_content.strip():
                return "기사 본문을 추출할 수 없었습니다. 웹사이트의 구조가 복잡하거나 콘텐츠가 동적으로 로드될 수 있습니다."

        # Truncate for API limit and clarity
        text_to_summarize = text_content[:8000]

        # Summarize using OpenAI
        if not OPENAI_API_KEY or "YOUR_OPENAI_API_KEY" in OPENAI_API_KEY:
            return "OpenAI API 키가 구성되지 않았습니다. 요약 기능을 사용할 수 없습니다."
        
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        summary_prompt = f"""당신은 원자재, 특히 니켈 구매를 담당하는 전문 매니저를 위한 AI 어시스턴트입니다.
        다음 뉴스 기사를 두 부분으로 나누어 분석해주세요.

        1. **기사 요약**: 기사의 핵심 내용을 객관적으로 2~3문장으로 요약합니다.
        2. **AI 인사이트**: 요약된 내용을 바탕으로, 이 정보가 니켈 가격(수급, 시장 심리 등)에 미칠 수 있는 영향을 분석합니다. 이 부분은 반드시 "**[AI 인사이트]**" 라는 말로 시작해야 합니다.

        ---
        [기사 본문]
        {text_to_summarize}
        ---

        분석 결과:
        """
        
        summary_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": summary_prompt}]
        )
        return summary_response.choices[0].message.content

    except requests.exceptions.HTTPError as e:
        return f"URL에 접근할 수 없습니다 (HTTP 오류 {e.response.status_code}). URL을 확인해주세요."
    except requests.exceptions.RequestException as e:
        return f"URL에서 콘텐츠를 가져오는 중 네트워크 오류가 발생했습니다: {e}"
    except Exception as e:
        import traceback
        return f"링크 요약 중 예상치 못한 오류가 발생했습니다: {e}\n{traceback.format_exc()}"


# --- Conversational AI (Not used by agent, for UI only) ---
def get_conversational_response(prompt):
    """Calls the OpenAI API to get a conversational response to the user's prompt."""
    system_prompt = """
당신은 니켈 시장을 전문으로 하는 구매 관리자를 위한 똑똑하고 친근한 AI 어시스턴트 '니켈봇'입니다.
당신의 답변은 유용하고, 명확하며, 흥미를 끄는 내용이어야 합니다.

**중요 지침:**
- 일반적인 질문(예: "안녕")에는 친근하게 대화체로 응답하세요.
- 사용자가 니켈 가격이나 전망에 대해 물으면, 다른 말 없이 `[PROVIDE_PREDICTION_AND_CONFIRM_ANALYSIS]` 토큰만 반환하세요.
- 사용자가 동의하고 상세 이유를 물으면(예: "응", "왜 그런지 알려줘", "분석해줘"), 확인 메시지와 함께 `[PERFORM_ANALYSIS]` 토큰으로 응답하세요.
- 사용자가 **더 많은 뉴스**를 요청하면(예: "다른 뉴스 없어?", "뉴스 더 보여줘", "show more news"), 확인 메시지와 함께 `[SHOW_MORE_NEWS]` 토큰으로 응답하세요.
- 사용자가 **다른 날짜**의 데이터를 보고 싶어하면(예: "5월 1일은 어땠어?", "show me may 1st"), 날짜를 파싱하여 YYYY-MM-DD 형식으로 만들고 `[CHANGE_DATE:YYYY-MM-DD]` 토큰으로 응답해야 합니다.
- 답변을 지어내지 마세요. 항상 제공된 도구와 토큰을 사용하세요.
"""
    try:
        if not OPENAI_API_KEY or "YOUR_OPENAI_API_KEY" in OPENAI_API_KEY:
            return "OpenAI API 키가 구성되지 않았거나 플레이스홀더입니다. .env 파일을 확인하고 'YOUR_OPENAI_API_KEY_HERE'를 실제 키로 교체해주세요."
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(st.session_state.get('messages', []))
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI와 통신하는 중 오류가 발생했습니다: {e}"

# --- UI Components (for UI page2 only) ---
def draw_price_graph(current_price, predicted_price):
    dates = ['현재', '7일 후']; prices = [current_price, predicted_price]
    fig = go.Figure(data=go.Scatter(x=dates, y=prices, mode='lines+markers', name='니켈 가격'))
    fig.update_layout(title="AI 기반 7일 가격 예측", yaxis_range=[min(prices)*0.95, max(prices)*1.05])
    st.plotly_chart(fig, use_container_width=True)

def draw_inventory_graph(current_stock, daily_usage, safety_stock, lead_time, simulation_weeks):
    days = np.arange(simulation_weeks * 7 + 1)
    projected_stock = current_stock - (daily_usage * days)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=days, y=projected_stock, name='예상 재고'))
    fig.add_trace(go.Scatter(x=days, y=[safety_stock]*len(days), name='안전 재고', line=dict(dash='dash')))
    fig.update_layout(title="재고 시뮬레이션")
    st.plotly_chart(fig, use_container_width=True)

# --- Main page2 UI function ---
def page2():
    st.header("2. 구매 (AI 의사결정 지원)")
    with st.spinner("데이터와 모델을 로드하는 중입니다..."):
        df_full, feature_cols = load_full_processed_data()
        model, scaler = load_model_and_scaler()
    if df_full is None: st.error("데이터 로딩 실패."); st.stop()

    # Session State
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = df_full.index.max().date()
    if 'messages' not in st.session_state: st.session_state.messages = []

    # Sidebar
    st.sidebar.date_input("예측 기준일 선택", value=st.session_state.selected_date, min_value=df_full.index.min().date(), max_value=df_full.index.max().date(), key="date_selector")
    
    # Data context
    selected_dt = pd.to_datetime(st.session_state.date_selector)
    current_context_data = df_full[df_full.index <= selected_dt].iloc[-1]
    current_price = current_context_data["Ni_price"]
    predicted_price = predict_price(model, feature_cols, current_context_data, scaler)
    if predicted_price is None: st.error("가격 예측 실패."); st.stop()

    # UI Layout
    st.subheader("핵심 지표")
    col1, col2 = st.columns(2)
    with col1: draw_price_graph(current_price, predicted_price)
    with col2: 
        plan_values = st.session_state.get('plan_values', {})
        draw_inventory_graph(plan_values.get('current_stock', 1000), plan_values.get('weekly_usage', 350)/7, plan_values.get('safety_stock', 200), plan_values.get('lead_time', 10), 8)
    st.markdown("---")
    st.subheader("AI 원인 분석 및 뉴스 연구원")
    for i, msg_data in enumerate(st.session_state.messages):
        message(msg_data["content"], is_user=(msg_data["role"] == "user"), key=f"chat_{i}", allow_html=True)
        
    if prompt := st.chat_input("가격 변동 분석, 링크 요약 또는 다른 질문을 입력하세요."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        message(prompt, is_user=True)
        
        # --- NEW LOGIC: Handle URL, price, and analysis questions ---
        url_match = re.search(r'https?://\S+', prompt)
        price_keywords = ["가격", "얼마", "예측", "전망", "7일"]
        analysis_keywords = ["분석", "이유", "왜"]
        
        # 0. User sent a URL for summarization
        if url_match:
            url = url_match.group(0)
            with st.spinner(f"링크를 분석하고 요약하는 중입니다..."):
                summary = summarize_url_content(url)
                st.session_state.messages.append({"role": "assistant", "content": summary})
            st.rerun()

        # 1. User asked for a price prediction (without analysis)
        elif any(keyword in prompt for keyword in price_keywords) and not any(keyword in prompt for keyword in analysis_keywords):
            price_change_percent = ((predicted_price - current_price) / current_price) * 100
            price_message = f"현재 니켈 가격은 **${current_price:,.2f}**이며, 7일 후 AI 예측 가격은 **${predicted_price:,.2f}**입니다. ({price_change_percent:+.2f}%)"
            st.session_state.messages.append({"role": "assistant", "content": price_message})
            st.session_state.messages.append({"role": "assistant", "content": "이 가격 변동의 원인에 대한 상세 분석을 원하시면 '분석해줘'라고 말씀해주세요."})
            st.rerun()

        # 2. User asked for a detailed analysis
        elif any(keyword in prompt for keyword in analysis_keywords):
            with st.spinner("AI 연구원이 뉴스를 요약하고 원인을 분석하는 중입니다..."):
                explainer = load_shap_explainer(model, scaler, df_full[feature_cols])
                analysis_result = perform_price_analysis(current_context_data, explainer, feature_cols, st.session_state.date_selector)
                
                response_text = ""
                if 'error' in analysis_result:
                    response_text = f"분석 중 오류 발생: {analysis_result['error']}"
                else:
                    response_text += analysis_result.get('main_factors_str', '')
                    if analysis_result.get('top_features'):
                        response_text += f"\n`(주요 변수: {', '.join(analysis_result['top_features'])})`\n\n"
                    if analysis_result.get('relevant_news'):
                        response_text += "관련 뉴스는 다음과 같습니다:\n\n---\n"
                        for item in analysis_result['relevant_news']:
                            score_display = "⭐" * item.get('relevance_score', 0)
                            response_text += f"#### [{item.get('title')}]({item.get('link')})\n**관련도 점수**: {score_display} ({item.get('relevance_score', 0)})\n> _{item.get('snippet', '')}_ \n\n"
                    else:
                        response_text += "\n\n관련된 뉴스를 찾지 못했습니다."
            st.session_state.messages.append({"role": "assistant", "content": response_text})
            st.rerun()

        # 3. For other general questions, use the existing LLM call
        else:
            with st.spinner("AI가 생각 중입니다..."):
                ai_response = get_conversational_response(prompt)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
            st.rerun()

# --- p8_agent가 호출할 실행 전용 함수 ---
def run_p2_purchase(state: dict) -> dict:
    """
    p8_agent를 위한 가격 예측 및 뉴스 분석 실행 함수.
    """
    try:
        df_full, feature_cols = load_full_processed_data()
        model, scaler = load_model_and_scaler()
        if df_full is None or model is None: return {"error": "p2: 모델 또는 데이터 로딩 실패"}

        # 1. 가격 예측 실행
        # p8 에이전트는 항상 최신 데이터를 기준으로 분석한다고 가정
        current_context_data = df_full.iloc[-1]
        selected_date = df_full.index.max().date()
        
        predicted_price = predict_price(model, feature_cols, current_context_data, scaler)
        if predicted_price is None: return {"error": "가격 예측 실패"}
        current_price = current_context_data["Ni_price"]
        price_trend = "stable"
        if predicted_price > current_price * 1.01: price_trend = "up"
        elif predicted_price < current_price * 0.99: price_trend = "down"
        
        price_result = {
            "current_price": float(current_price),
            "predicted_price": float(predicted_price),
            "price_trend": price_trend
        }

        # 2. SHAP 및 뉴스 분석 실행 (가격 상승 또는 하락 시에만)
        if price_trend in ["up", "down"]:
            explainer = load_shap_explainer(model, scaler, df_full[feature_cols])
            if explainer:
                analysis_result = perform_price_analysis(current_context_data, explainer, feature_cols, selected_date)
                if 'error' not in analysis_result:
                    # 가격 예측 결과와 뉴스 분석 결과를 합쳐서 반환
                    price_result.update(analysis_result)

        return price_result
        
    except Exception as e:
        import traceback
        return {"error": f"p2 실행 중 예외 발생: {e}", "trace": traceback.format_exc()}