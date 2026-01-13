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
[상세보기 · WIKI](https://github.com/chrochet/Multi-agnet-with-nickelscm-/wiki/Streamlit-UI)
* 사용자 입력 기반(재고/수요/리드타임) 분석 
* 멀티페이지로 에이전트별 기능 제공(P1~P7)
* 

---

### 02. P8: Agent Master (멀티에이전트 오케스트레이터)
[상세보기 · WIKI](https://github.com/chrochet/Multi-agnet-with-nickelscm-/wiki/P8-multi%E2%80%90agent-router)
* 질문 의도 분류 → 관련 에이전트 라우팅
* P1-P7 결과를 통합해 **최종 의사결정 리포트**(P8)로 도출 

---

### 03. P2: Purchase Agent (ML + 니켈예측 + RAG)
[상세보기 · WIKI](https://github.com/chrochet/Multi-agnet-with-nickelscm-/wiki/P2-Purchase-Agent)
* 니켈 가격 예측(ML) 기반 구매 타이밍/수량 추천
* 뉴스/기사 RAG로 시장 이슈 반영, 근거 요약 제공
* (옵션) SHAP 기반 XAI 적용

---

### 04. P3: Customs Agent (Tool Call + RAG)
[상세보기 · WIKI](https://github.com/chrochet/Multi-agnet-with-nickelscm-/wiki/P3-Customs-Agent)
* HS Code/관세/통관 규정 질의 대응
* Tool Call(API) + 문서 RAG로 근거 기반 답변 제공

---

### 05. Support Agents (P1 ~ P7)
[상세보기 · WIKI](https://github.com/chrochet/Multi-agnet-with-nickelscm-/wiki/SCM-Support-Agents(P1-P4-P5-P6-P7))
* P1 Plan / P4 Logistics / P5 Quality / P6 Finance / P7 Inventory 
* 핵심 기능을 보완하는 확장형 보조 모듈

---















