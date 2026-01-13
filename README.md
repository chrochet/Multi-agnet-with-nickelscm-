# Multi-agnet-with-nickelscm-
**니켈 구매 의사결정 지원을 위한 멀티에이전트 기반 RAG SCM 시스템 (Streamlit)**

---

## 🖥️ 프로젝트 소개
본 프로젝트는 니켈 가격 변동성을 반영하여 머신러닝을 통해 구매 타이밍을 예측하고, 가격에 따른 SCM 의사결정(구매 타이밍 및 발주 의사결정)을 지원하는 멀티에이전트 기반 RAG 시스템입니다. 

---

## 🕰️ 개발 기간
- 2025.10.15 - 2025.12.15

---

## 🧑‍🤝‍🧑 멤버 구성
- 유지현
- 김**
- 권**


## 🏆 AI캡스톤디자인 최우수상(1위) 



## 🧩 Multi-agent 시스템 구조
<img width="1500" height="861" alt="image" src="https://github.com/user-attachments/assets/95eed977-37dd-4c5f-970c-6883bb462bde" />

<img width="1304" height="675" alt="image" src="https://github.com/user-attachments/assets/3f204e47-a1e3-4b18-9404-ee000b1124a5" />

<img width="1892" height="717" alt="image" src="https://github.com/user-attachments/assets/98a3563a-d7f3-44ba-9cff-2db4207a7653" />


---

## ⚙️ 개발 환경

* Python **3.11+**
* IDE : VSCode / PyCharm
* Frontend : **Streamlit**
* Vector DB : **ChromaDB**
* LLM API : **OpenAI API**

### Framework / Library

* streamlit
* langchain
* langchain-chroma
* langchain-openai
* chromadb
* pandas
* numpy
* httpx

---

## 📁 프로젝트 구조

```text
.
├── app.py                     # Streamlit 메인 실행 파일
├── p8_agent.py                # ⭐ Agent Master (오케스트레이션/라우팅)
├── mypages/                   # Streamlit 멀티페이지 구성
│   ├── p1_plan.py
│   ├── p2_purchase.py          # ⭐ 핵심: 구매 의사결정
│   ├── p3_customs.py           # ⭐ 핵심: HS/관세/통관
│   ├── p4_logistics.py
│   ├── p5_quality.py
│   ├── p6_finance.py
│   └── p7_inventory.py
├── modules/                   # 공통 모듈(데이터/툴/유틸)
│   ├── data_loader.py
│   ├── retriever.py            # RAG Retriever
│   ├── tools.py                # Tool Call 모듈(API 등)
│   └── utils.py
├── data/                      # 원천/가공 데이터
├── vectordb/                  # 로컬 ChromaDB 저장소(Git 제외)
├── requirements.txt
├── runtime.txt
├── .gitignore
└── .env.example
```

---

## 📌 주요 기능

### 01. Streamlit UI (app.py)

* **사용자 입력 기반 분석 실행**: 재고/수요/리드타임 등 니켈 구매 의사결정 조건을 입력
* **멀티페이지 UI**로 에이전트별 기능을 분리 제공(P1~P7)
* 사용자의 질의/조건을 **P8 Agent Master로 전달**하여 최종 통합 리포트 출력

---

### 02. P8: Agent Master (멀티에이전트 오케스트레이터)

* 사용자 질문을 분석하여 **의도 분류(Intent Routing)** 수행
* 상황에 맞는 전문가 에이전트(P1~P7)를 **선택적으로 호출**
* 특히 **핵심 에이전트 P2(구매)·P3(통관)** 결과를 통합하여

  * 결론(발주 필요/불필요)
  * 근거(수치/문서/툴콜 결과)
  * 리스크 요약
    형태로 **최종 의사결정 리포트**를 생성

---

### 03. P2: Purchase Agent (머신러닝 + 니켈예측 RAG)

* **니켈 가격 예측(ML)** 기반으로 구매 타이밍 분석
* 뉴스/기사 등 외부 텍스트를 수집하여 **RAG 기반 시장 이슈 반영**
* 예측 결과와 검색 근거를 결합해

  * 발주 타이밍/수량
  * 주요 변수 근거
    를 설명가능하게 제시
* (선택) SHAP 기반 **설명가능성(XAI)** 적용

---

### 04. P3: Customs Agent (Tool Call + RAG)

* HS Code / 관세 / 통관 규정 관련 질의에 대응
* **Tool Call(API 호출)** 로 관세율·규정 등 정보를 실시간 조회
* 관련 문서/스펙시트 등을 **RAG로 검색**하여 근거 기반 요약 제공
* 구매 판단 시 **통관 비용·리스크 요소를 함께 반영**할 수 있도록 지원

---

### 05. Support Agents (P1 ~ P7)

핵심은 P8(통합) + P2/P3(핵심 실행)이며, 나머지 에이전트들은 **확장 가능한 보조 모듈**로 구성됩니다.

* **P1 Plan**: 수요 기반 구매 계획/시나리오 보조
* **P4 Logistics**: 물류 일정/ETA/운송 리스크 보조
* **P5 Quality**: 품질 검사 기준/합격 흐름 보조
* **P6 Finance**: 비용·환율·결제조건 기반 재무 영향 분석
* **P7 Inventory**: FIFO 기반 재고 현황/재주문점 분석 및 발주 메일 생성






