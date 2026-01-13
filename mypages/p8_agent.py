# mypages/p8_agent.py

import streamlit as st
from typing import TypedDict, Any, Dict, List
import time
import os
import pandas as pd

# 1. 각 전문 에이전트(Skill Agent)의 실행 함수 임포트
from mypages.p2_purchase import run_p2_purchase
from mypages.p3_customs import run_p3_customs
from mypages.p4_logistics import run_p4_logistics
from mypages.p5_quality import run_p5_quality
from mypages.p6_finance import run_p6_finance
from mypages.p7_inventory import run_p7_inventory

# 2. 공유 상태(AgentState) 정의
class AgentState(TypedDict, total=False):
    user_question: str
    p1_plan: Dict[str, Any]
    executed_agents: List[str]
    pending_agents: List[str]
    agent_outputs: Dict[str, Dict]
    conclusion: Dict[str, Any]
    recommendations: List[str]
    confidence: Dict[str, Any]
    agent_summaries: Dict[str, Dict[str, Any]]

# 3. Meta Agent (Orchestrator) 정의
class MetaAgent:
    def __init__(self, user_question: str, p1_plan: dict):
        self.state: AgentState = {
            "user_question": user_question,
            "p1_plan": p1_plan,
            "executed_agents": ['p1'], "pending_agents": [], "agent_outputs": {},
            "conclusion": {}, "recommendations": [], "confidence": {}, "agent_summaries": {}
        }
        self.agent_map = {
            'p2': run_p2_purchase, 'p3': run_p3_customs, 'p4': run_p4_logistics,
            'p5': run_p5_quality, 'p6': run_p6_finance, 'p7': run_p7_inventory,
        }
        self.agent_dependencies = {'p6': ['p2', 'p3', 'p7']}
        self.agent_info = {
            'p2': {'icon': '📈', 'title': '구매 가격 분석'}, 'p3': {'icon': '🚢', 'title': '수입 통관 분석'},
            'p4': {'icon': '🚚', 'title': '운송 및 물류 분석'}, 'p5': {'icon': '🔬', 'title': '품질 관리 분석'},
            'p6': {'icon': '💰', 'title': '재무 및 원가 분석'}, 'p7': {'icon': '📦', 'title': '재고 관리 분석'},
        }

    def _initial_planning(self):
        user_question = self.state['user_question'].lower()
        plan = set()
        if any(k in user_question for k in ['재고','수량']): plan.add('p7')
        if any(k in user_question for k in ['가격','시세','구매']): plan.add('p2')
        if any(k in user_question for k in ['통관','관세']): plan.add('p3')
        if any(k in user_question for k in ['물류','운송']): plan.add('p4')
        if any(k in user_question for k in ['품질']): plan.add('p5')
        if any(k in user_question for k in ['원가','비용','재무']): plan.add('p6')
        
        if not plan or any(k in user_question for k in ['종합','전체','분석']):
            plan.update(['p7', 'p2', 'p4', 'p6'])

        full_plan = set(plan)
        for agent in plan:
            full_plan.update(self.agent_dependencies.get(agent, []))
        self.state['pending_agents'] = sorted(list(full_plan))

    def _evaluate_and_replan(self):
        outputs = self.state['agent_outputs']
        newly_added = set()

        if outputs.get('p7', {}).get('risk_level') == 'warning':
            for agent in ['p2', 'p6', 'p4']:
                if agent not in self.state['executed_agents'] and agent not in self.state['pending_agents']:
                    newly_added.add(agent)
        
        if outputs.get('p2', {}).get('price_trend') in ['up', 'down']:
            if 'p6' not in self.state['executed_agents'] and 'p6' not in self.state['pending_agents']:
                newly_added.add('p6')
        
        if newly_added:
            final_new = set(newly_added)
            for agent in newly_added:
                st.toast(f"ℹ️ 연관 분석: {self.agent_info[agent]['title']}을 추가 실행합니다.")
                final_new.update(self.agent_dependencies.get(agent, []))
            
            self.state['pending_agents'].extend([a for a in final_new if a not in self.state['executed_agents'] and a not in self.state['pending_agents']])
            self.state['pending_agents'] = sorted(list(set(self.state['pending_agents'])))

    def _generate_structured_report(self):
        outputs = self.state['agent_outputs']
        all_agents = set(self.agent_map.keys())
        executed = set(a for a in self.state['executed_agents'] if a != 'p1')
        
        # Confidence
        executed_count, total_count = len(executed), len(all_agents)
        level = "낮음" if executed_count < total_count / 2 else "보통" if executed_count < total_count else "높음"
        missing = [self.agent_info[a]['title'] for a in sorted(all_agents - executed) if a in self.agent_info]
        reason = f"총 {total_count}개 중 {executed_count}개 에이전트 실행." + (f" ({', '.join(missing)} 미실행)" if missing else "")
        self.state['confidence'] = {"level": level, "reason": reason, "executed_count": executed_count, "total_count": total_count}

        # Summaries
        self.state['agent_summaries'] = {}
        for name in sorted(all_agents):
            info = self.agent_info.get(name, {})
            result = outputs.get(name)
            summary, status, details = "분석 계획에 포함되지 않음.", "skipped", {}
            if name in executed:
                if result and not result.get('error'):
                    status, details = "success", result
                    if name == 'p7': summary = f"재고 리스크: {result.get('risk_level', 'N/A').upper()}"
                    elif name == 'p2': summary = f"가격 예측: {result.get('price_trend', 'N/A').upper()} 추세"
                    elif name == 'p4': summary = f"운송 리스크: {result.get('delay_risk', 'N/A').upper()}"
                    elif name == 'p5': summary = f"품질 등급: {result.get('status', 'N/A')}"
                    elif name == 'p3': summary = f"관세 리스크: {result.get('risk_level', 'N/A').upper()}"
                    elif name == 'p6': summary = f"예상 총 원가: ₩{result.get('total_cost', 0):,.0f}"
                else: status, summary = "error", f"오류: {result.get('error', '알수없음') if result else '결과없음'}"
            elif name in self.state['pending_agents']: status, summary = "pending", "의존성 대기"
            self.state['agent_summaries'][name] = {'icon': info.get('icon'), 'title': info.get('title'), 'summary': summary, 'status': status, 'details': details}

        # Conclusion & Recommendations with News Analysis Integration
        p7_out, p2_out = outputs.get('p7', {}), outputs.get('p2', {})
        conclusion = {"level": "info", "message": "요청된 분석에 대한 명확한 결론을 내리기 어렵습니다."}
        recs = ["[권고] 주기적인 시장 모니터링을 통해 유리한 구매 시점을 탐색하는 것이 좋습니다."]
        
        # 뉴스 분석 결과를 결론에 통합
        news_factor_str = ""
        if p2_out.get('main_factors_str'):
             # "주요 가격 변동 요인은" 부분을 제거하고 핵심만 사용
            news_factor_str = p2_out['main_factors_str'].replace("주요 가격 변동 요인은", "").replace("(으)로 보입니다.", "").strip()

        if p7_out.get('risk_level') == 'warning':
            recs = ["[권고] 생산 차질 방지를 위해, 최소 필요 물량(안전재고)에 대한 구매를 즉시 시작하는 것이 안전합니다."]
            if p2_out.get('price_trend') == 'up':
                base_message = "재고 부족과 가격 상승 위험이 동시에 발생하여, 즉각적인 대응이 필요한 매우 부정적인 상황입니다."
                if news_factor_str: base_message += f" 특히, **{news_factor_str}**로 인해 가격 상승 압력이 있습니다."
                conclusion = {"level": "critical", "message": base_message}
            else:
                conclusion = {"level": "warning", "message": "재고 부족이 가장 시급한 문제입니다. 생산 차질 방지를 위해 즉시 구매가 필요합니다."}

        elif p7_out.get('risk_level') == 'safe':
            if p2_out.get('price_trend') == 'up':
                base_message = "재고는 안전하지만, 향후 가격 상승이 예상됩니다."
                if news_factor_str: base_message += f" **{news_factor_str}**의 영향으로, 비용 절감을 위해 선제적인 구매를 고려할 수 있습니다."
                else: base_message += " 비용 절감을 위해 선제적인 구매를 고려할 수 있습니다."
                conclusion = {"level": "info", "message": base_message}
                recs = ["[권고] 단기적인 긴급 구매는 불필요합니다.", "[제안] 장기적인 관점에서 가격이 더 오르기 전에 미리 구매하여 비용을 절감하는 전략을 고려해볼 수 있습니다."]
            elif p2_out.get('price_trend') == 'down':
                conclusion = {"level": "success", "message": "재고가 안정적이고 가격 하락이 예상되는, 매우 긍정적인 상황입니다."}
                recs = ["[권고] 구매를 서두를 필요가 없습니다.", "[제안] 가격이 충분히 하락했을 때 구매하여 비용을 최적화하는 것이 좋습니다."]
            else: # 재고 안정, 가격 안정
                conclusion = {"level": "success", "message": "재고와 가격 모두 안정적인 상황입니다."}
                recs = ["[권고] 긴급 구매 요인은 없으며, 현재 가격 수준에서 필요에 따라 구매를 진행할 수 있습니다."]
        
        self.state['conclusion'], self.state['recommendations'] = conclusion, recs

    def run(self):
        self._initial_planning()
        if not self.state['pending_agents']:
            self.state.update({"conclusion": {"level": "info", "message": "실행할 분석 에이전트가 없습니다."},"confidence": {"level": "낮음", "reason": "분석할 에이전트가 없습니다.", "executed_count": 0, "total_count": len(self.agent_map)}})
            return self.state
        for _ in range(10):
            if not self.state['pending_agents']: break
            executable = next((a for a in sorted(self.state['pending_agents']) if all(d in self.state['executed_agents'] for d in self.agent_dependencies.get(a, []))), None)
            if executable:
                self.state['pending_agents'].remove(executable)
                with st.spinner(f"💡 {self.agent_info[executable]['title']} 분석 실행 중..."):
                    try: result = self.agent_map[executable](self.state) or {"error": "결과 없음"}
                    except Exception as e: result = {"error": f"실행 중 예외: {e}"}
                self.state['agent_outputs'][executable] = result
                self.state['executed_agents'].append(executable)
                self._evaluate_and_replan()
            else: break
        
        self._generate_structured_report()
        return self.state

# --- 4. UI 렌더링 함수들 ---
def render_details_content(agent_name, details):
    st.markdown("---")
    if agent_name == 'p2':
        st.metric(label="현재 니켈 가격", value=f"${details.get('current_price', 0):,.2f}")
        st.metric(label="7일 후 AI 예측 가격", value=f"${details.get('predicted_price', 0):,.2f}")
        st.markdown(f"**가격 추세**: `{details.get('price_trend', 'N/A').upper()}`")
        if details.get('relevant_news'):
            st.markdown("**주요 뉴스 분석:**")
            st.info(details.get('main_factors_str', ''))
            for news in details.get('relevant_news', []):
                st.markdown(f"- [{news.get('title')}]({news.get('link')})")
                st.caption(f"> {news.get('snippet')}")
    elif agent_name == 'p7':
        st.metric(label="현재 총 재고량", value=f"{details.get('current_inventory', 0) / 1000:,.2f} t")
        st.metric(label="재주문점 (ROP)", value=f"{details.get('reorder_point', 0) / 1000:,.2f} t")
        shortage = details.get('shortage_qty', 0) / 1000
        st.metric(label="부족 또는 여유 수량", value=f"{abs(shortage):,.2f} t", delta=f"{-shortage:,.2f} t", delta_color="inverse" if shortage > 0 else "normal")
    elif agent_name == 'p3':
        st.metric(label="예상 관세율 (MFN)", value=f"{details.get('mfn_rate', 0):.1f} %")
        st.markdown(f"**관세 리스크**: `{details.get('risk_level', 'N/A').capitalize()}`")
        st.info(f"**AI 답변 요약**: {details.get('answer', '정보 없음')}")
    elif agent_name == 'p4':
        st.markdown(f"**발주 번호**: `{details.get('po_number', 'N/A')}`")
        st.markdown(f"**현재 상태**: `{details.get('current_status', 'N/A')}`")
        st.metric(label="도착까지 남은 기간 (ETA)", value=f"{details.get('eta_days', 0)} 일")
        st.markdown(f"**운송 지연 리스크**: `{details.get('delay_risk', 'N/A').capitalize()}`")
    elif agent_name == 'p5':
        st.markdown(f"**분석 대상 공급사**: `{details.get('supplier', 'N/A')}`")
        st.metric(label="SRM 등급", value=details.get('status', '정보 없음'))
        st.markdown(f"**권고 조치**: {details.get('action', 'N/A')}")
    elif agent_name == 'p6':
        st.metric(label="예상 총 구매원가", value=f"₩ {details.get('total_cost', 0):,.0f}")
        st.info(f"**AI 추천 공급사**: `{details.get('best_supplier', 'N/A')}` (단가: `${details.get('selected_price_usd', 0):,.2f}`)")
    else: st.json(details)

def render_dashboard(state):
    st.title("🤖 AI 구매 의사결정 대시보드")
    if state.get('conclusion'): st.info(f"**종합 결론**: {state['conclusion'].get('message', '')}")
    st.markdown("---")
    if state.get('agent_summaries'):
        st.subheader("📊 에이전트별 상세 분석")
        cols = st.columns(3)
        for i, (name, data) in enumerate(sorted(state['agent_summaries'].items())):
            with cols[i % 3]:
                color = {"success": "#28a745", "error": "#dc3545", "pending": "#ffc107"}.get(data['status'], "#6c757d")
                st.markdown(f"""<div style="border: 1.5px solid {color}; border-radius: 10px; padding: 15px; margin-bottom: 10px; min-height: 110px;">
                    <h6>{data['icon']} {data['title']}</h6>
                    <small>{data['summary']}</small>
                </div>""", unsafe_allow_html=True)
                if data['status'] == 'success' and data['details']:
                    with st.expander("자세히 보기"): render_details_content(name, data['details'])
                elif data['status'] == 'error':
                    with st.expander("오류 상세", expanded=True): st.error(data['summary'])
    st.markdown("---")
    if state.get('recommendations'):
        st.subheader("💡 행동 제안"); [st.markdown(f"- {rec}") for rec in state['recommendations']]
    if state.get('confidence'):
        conf = state['confidence']
        st.subheader("✅ 최종 판단 신뢰도")
        st.metric(label="분석 신뢰도", value=conf['level']); st.progress(conf['executed_count'] / conf['total_count'] if conf['total_count'] > 0 else 0)
        st.caption(conf['reason'])

# --- 5. Main Entrypoint ---
def p8_agent_main(user_question: str):
    if 'plan_values' not in st.session_state: st.session_state.plan_values = {}
    required_keys = ['order_qty', 'current_stock']
    if not all(key in st.session_state.plan_values and st.session_state.plan_values[key] is not None for key in required_keys):
        st.warning("AI 분석을 시작하려면 '2. 구매' 페이지의 사이드바 또는 '1. 계획' 페이지에서 시뮬레이션 정보를 먼저 입력해야 합니다.")
        missing_keys = [key for key in required_keys if key not in st.session_state.plan_values or st.session_state.plan_values[key] is None]
        st.info(f"현재 입력되지 않은 필수 정보: {', '.join(missing_keys)}")
        st.stop()
    
    meta_agent = MetaAgent(user_question, st.session_state.plan_values)
    final_state = meta_agent.run()
    render_dashboard(final_state)
