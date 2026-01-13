import json
from typing import Any, Dict, List

from openai import OpenAI

from .hybrid_search import HybridSearcher
from .agent_tools import CustomsTools


# ============================================================
# 📌 Advanced RAG + Router + ToolCall + HybridSearcher
# ============================================================

class AdvancedRAG:
    """
    관세/통관 전용 RAG 엔진 (최종 안정 버전)

    - Query Router(JSON Schema)
    - 국가/품목 NER
    - ToolCall 2종 (관세계산 / MFN 조회)
    - Hybrid RAG(BM25 + Dense fallback)
    - Streamlit과 완전 호환
    """

    def __init__(self, df, chroma_collection):
        self.df = df
        self.collection = chroma_collection

        self.searcher = HybridSearcher(df, chroma_collection)
        self.tools = CustomsTools(df)
        self.client = OpenAI()

    # ============================================================
    # 0) 행동 정규화 헬퍼
    # ============================================================

    def _normalize_action(
        self,
        raw_action: str,
        question: str,
        rate: Any,
        amount: Any,
    ) -> str:
        """
        Router가 준 '행동' 문자열(한국어/영어 섞임)을
        내부 모드 값으로 정규화한다.
        """
        s = (raw_action or "").strip()
        base = s.replace(" ", "").upper()

        # 기본 매핑
        if base in ("TOOL_SEARCH_TARIFF", "SEARCH_TARIFF", "TOOLSEARCHTARIFF"):
            action = "TOOL_SEARCH_TARIFF"
        elif base in ("TOOL_CALCULATE", "CALCULATE", "CALC"):
            action = "TOOL_CALCULATE"
        elif base in ("TOOL_HS_LOOKUP", "HS_LOOKUP", "HSLOOKUP"):
            # HS LOOKUP도 결국 관세 조회로 처리
            action = "TOOL_SEARCH_TARIFF"
        elif base in ("SEARCH", "검색"):
            action = "SEARCH"
        else:
            # 애매한 경우: 질문 안에 MFN / 관세가 있으면 관세조회로 추정
            q = question.lower()
            if "mfn" in q or "관세" in q:
                action = "TOOL_SEARCH_TARIFF"
            else:
                action = "SEARCH"

        # 금액 + 세율이 나오면 계산 모드로 보정
        q_lower = question.lower()
        if any(k in q_lower for k in ["cif", "금액", "얼마", "부담"]) and rate not in (None, 0):
            action = "TOOL_CALCULATE"

        return action

    # ============================================================
    # 1) 질문 분석기 (Router + NER)
    # ============================================================

    def analyze_query(self, question: str) -> Dict[str, Any]:
        """
        Router가 모드(mode) / 국가 / 품목 / 세율 / 금액을 해석한다.
        출력은 항상 dict 보장.
        """
        system_prompt = """
        너는 관세·통관 전용 Router야.
        질문을 보고 아래 JSON 항목을 채워라.

        - "행동":
            - "SEARCH"             : 일반 RAG 검색
            - "TOOL_SEARCH_TARIFF" : 특정 국가+품목 MFN 조회
            - "TOOL_CALCULATE"     : 세율 기반 관세 계산
            - "TOOL_HS_LOOKUP"     : HS 코드 후보 조회
            - "OTHER"              : 그 외 일반 질문

        - "국가"  : 예) 일본, 중국, 한국 (없으면 "")
        - "품목"  : 예) 철광석, 니켈, 자동차부품 (없으면 "")
        - "율"    : 세율 숫자(%) 혹은 null
        - "금액"  : CIF 또는 과세가격 숫자 혹은 null

        JSON 이외의 텍스트는 절대 출력하지 마.
        """

        schema = {
            "type": "object",
            "properties": {
                "행동": {"type": "string"},
                "국가": {"type": "string"},
                "품목": {"type": "string"},
                "율": {"type": ["number", "null"]},
                "금액": {"type": ["number", "null"]},
            },
            "required": ["행동"],
            "additionalProperties": True,
        }

        try:
            res = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "router", "schema": schema},
                },
            )
            parsed = json.loads(res.choices[0].message.content)
        except Exception:
            parsed = {"행동": "SEARCH", "국가": "", "품목": "", "율": None, "금액": None}

        raw_action = (parsed.get("행동") or "").strip()
        country = parsed.get("국가") or ""
        item = parsed.get("품목") or ""
        rate = parsed.get("율")
        amount = parsed.get("금액")

        # 한국어/변형 행동 문자열을 내부 모드로 정규화
        mode = self._normalize_action(raw_action, question, rate, amount)

        return {
            "mode": mode,          # 내부에서 사용하는 통일된 모드
            "action": mode,        # UI에서 보여줄 용도
            "raw_action": raw_action,  # Router가 준 원래 문자열
            "country": country,
            "item": item,
            "rate": rate,
            "amount": amount,
            "raw_router": parsed,
            "원시_질문": question,
        }

    # ============================================================
    # 2) 계산 ToolCall (세율 기반 관세 계산기)
    # ============================================================

    def _run_calculation_tool(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        rate = analysis.get("rate")
        amount = analysis.get("amount")

        if rate is None or amount is None:
            return {
                "text": "세율(%) 또는 금액이 부족해 계산할 수 없습니다.",
                "result": {},
            }

        try:
            rate_f = float(rate)
            amount_f = float(amount)
        except Exception:
            return {"text": "세율/금액을 숫자로 해석하지 못했습니다.", "result": {}}

        duty = amount_f * (rate_f / 100.0)

        msg = (
            "🧮 **MFN 관세 계산 결과**\n\n"
            f"- 과세가격(CIF 등): {amount_f:,.0f}\n"
            f"- MFN 세율: {rate_f:.2f}%\n"
            f"- 추정 관세액: {duty:,.0f}\n\n"
            "※ 실제 관세는 감면·면제, 부가세, 기타 세목을 고려해 관세사가 최종 확정합니다."
        )

        return {"text": msg, "result": {"amount": amount_f, "rate": rate_f, "duty": duty}}

    # ============================================================
    # 3) Hybrid RAG 파이프라인 (BM25 중심)
    # ============================================================

    def rag_pipeline(self, question: str, router: Dict[str, Any]) -> Dict[str, Any]:
        hits = self.searcher.search(question, top_k=20)

        if not hits:
            return {
                "answer": "관련 관세 데이터를 찾지 못했습니다.",
                "sources": [],
            }

        country = (router.get("country") or "").strip()
        item = (router.get("item") or "").strip()

        filtered = hits

        # 1) 국가 필터
        if country:
            temp = []
            for h in hits:
                if country in str(h["row"].get("country", "")):
                    temp.append(h)
            if temp:
                filtered = temp

        # 2) 품목 필터
        if item:
            temp = []
            for h in filtered:
                row = h["row"]
                blob = " ".join(
                    [
                        str(row.get("desc", "")),
                        str(row.get("kor_desc", "")),
                        str(row.get("note", "")),
                    ]
                )
                if item in blob:
                    temp.append(h)
            if temp:
                filtered = temp

        # 상위 5개만 사용
        filtered = filtered[:5]

        context_lines: List[str] = []
        source_info: List[Dict[str, Any]] = []

        for h in filtered:
            row = h["row"]
            hs = row.get("hs_code", "")
            desc = row.get("desc", "")
            mfn = row.get("mfn_rate", "")
            cty = row.get("country", "")
            src = row.get("source_file", "")
            hs2 = row.get("hs2", "")

            context_lines.append(
                f"국가: {cty}, HS: {hs}, MFN: {mfn}, 품목: {desc}, 파일: {src}"
            )

            source_info.append(
                {
                    "country": cty,
                    "hs_code": hs,
                    "desc": desc,
                    "mfn_rate": mfn,
                    "source_file": src,
                    "hs2": hs2,
                }
            )

        context = "\n".join(context_lines)

        final = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 관세·통관 RAG 전문가다. "
                        "아래 제공된 문서를 기반으로만 답변해라. "
                        "문서에 없으면 추측하지 말고 '데이터 없음'이라고 말한다."
                    ),
                },
                {"role": "assistant", "content": f"참고 문서:\n{context}"},
                {"role": "user", "content": question},
            ],
        )

        return {
            "answer": final.choices[0].message.content,
            "sources": source_info,
        }

    # ============================================================
    # 4) 엔트리 포인트 (Streamlit에서 호출)
    # ============================================================

    def generate_answer(self, question: str) -> Dict[str, Any]:
        analysis = self.analyze_query(question)
        mode = analysis.get("mode", "SEARCH")

        # 1) 계산 모드
        if mode in ("TOOL_CALCULATE", "CALCULATE", "계산"):
            calc = self._run_calculation_tool(analysis)
            return {
                "answer": calc["text"],
                "sources": [],
                "analysis": analysis,
            }

        # 2) 국가/품목이 명확 → Tool 기반 MFN 조회
        if mode in ("TOOL_SEARCH_TARIFF", "도구검색관세"):
            rows = self.tools.search_tariff(
                country=analysis.get("country", ""),
                item=analysis.get("item", ""),
            )
            if rows:
                msg = [
                    f"**국가:** {analysis.get('country') or '미지정'} | "
                    f"**품목:** {analysis.get('item') or '미지정'}",
                    "상위 관세 정보입니다:\n",
                ]
                for r in rows[:5]:
                    msg.append(
                        f"- HS {r.get('hs_code')}: {r.get('desc')} "
                        f"| MFN: {r.get('mfn_rate')}"
                    )
                msg.append("\n※ 보다 정확한 판단은 관세사와의 상담이 필요합니다.")

                return {
                    "answer": "\n".join(msg),
                    "sources": rows,
                    "analysis": analysis,
                }

        # 3) 전체 fallback: Hybrid RAG
        rag = self.rag_pipeline(question, analysis)
        rag["analysis"] = analysis
        return rag


# ============================================================
# ✔ Streamlit용 Factory 함수
# ============================================================

def get_rag_engine(df, collection):
    """
    Streamlit에서 호출하기 위한 안전한 wrapper.
    """
    return AdvancedRAG(df=df, chroma_collection=collection)
