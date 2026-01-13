# /Users/gwongayoung/캡디 팀플/니켈_캡스톤/gayoung/quality_manager.py

import os
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
import json
from pypdf import PdfReader
from datetime import datetime

# --- 1. 환경 변수 및 경로 설정 ---
try:
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
    parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
    dotenv_path = os.path.join(parent_dir, '.env')
    load_dotenv(dotenv_path=dotenv_path)
except Exception:
    script_dir = os.getcwd()

API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=API_KEY) if API_KEY else None

# --- 2. 상수 및 기본 설정 ---
DB_FILE = os.path.join(script_dir, 'quality_db.csv')
COLUMNS = [
    '날짜', '공급사명', 'Lot No', '수량',
    'coa_ni', 'coa_moisture', 'coa_fe', 'coa_s', 'coa_p',
    'actual_ni', 'actual_moisture', 'actual_fe', 'actual_s', 'actual_p',
    '판정', '비고'
]
SPECS = {
    'ni': {'label': '니켈'},
    'moisture': {'label': '수분'},
    'fe': {'label': '철'},
    's': {'label': '황'},
    'p': {'label': '인'}
}

def load_or_create_db():
    """데이터베이스 파일을 로드하거나 없으면 새로 생성합니다."""
    if not os.path.exists(DB_FILE):
        pd.DataFrame(columns=COLUMNS).to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    return pd.read_csv(DB_FILE)

# --- 3. PDF 데이터 추출 기능 (기존 유지) ---
def extract_data_from_pdf(pdf_file):
    """pypdf로 PDF 텍스트를 추출하고, OpenAI API를 이용해 주요 정보를 JSON 형태로 파싱합니다."""
    if not client:
        print("DEBUG: OpenAI client is not initialized.")
        raise ConnectionError("OpenAI API 키가 설정되지 않았습니다.")
    
    response_content = "" # 응답 내용을 담을 변수 초기화
    try:
        print("DEBUG: Starting PDF processing...")
        reader = PdfReader(pdf_file)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        print(f"DEBUG: Extracted {len(text)} characters from PDF.")

        if not text.strip():
            print("DEBUG: No text could be extracted from the PDF.")
            return None, "PDF에서 텍스트를 추출할 수 없습니다. (내용이 없거나 이미지 파일일 수 있습니다)"

        prompt = f"다음 텍스트에서 공급사(supplier), Lot 번호(lot_no), 총 중량(quantity), 니켈(ni), 수분(moisture), 철(fe), 황(s), 인(p) 값을 JSON으로 추출해줘.\n- 규칙: 숫자만 추출하고 단위(%)는 제거. 찾을 수 없으면 null.\n- 텍스트: {text[:4000]}\n- JSON 출력:"
        
        print("DEBUG: Sending prompt to OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        
        response_content = response.choices[0].message.content
        print(f"DEBUG: Received response from OpenAI: {response_content}")
        
        return json.loads(response_content), "추출 성공"
    except json.JSONDecodeError as je:
        print(f"DEBUG: JSONDecodeError - {je}")
        return None, f"AI 모델이 유효한 JSON을 반환하지 않았습니다. 응답: {response_content}"
    except Exception as e:
        print(f"DEBUG: An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return None, f"PDF 처리 중 오류 발생: {e}"

# --- 4. 품질 평가 및 저장 기능 (SRM 로직 강화) ---
def assess_and_save_quality(date, supplier, lot_no, quantity, coa_values, actual_values):
    """
    실측값(actual)과 COA 값을 비교하여 '데이터 신뢰성'을 평가하고 결과를 CSV에 저장합니다.
    - 니켈(Ni): 실측 >= COA 이어야 합격
    - 그 외(수분, Fe, S, P): 실측 <= COA 이어야 합격
    """
    final_status = "합격"
    remarks = []
    
    # 각 항목의 레이블을 쉽게 찾기 위해 SPECS 활용
    component_labels = {key: spec['label'] for key, spec in SPECS.items()}

    # 1. 니켈(Ni) 검사
    ni_actual = actual_values.get('ni')
    ni_coa = coa_values.get('ni')
    if ni_actual is not None and ni_coa is not None:
        if ni_actual < ni_coa:
            final_status = "불합격"
            remarks.append(f"{component_labels.get('ni', '니켈')} 데이터 신뢰성 위반")

    # 2. 그 외 성분 검사 (수분, Fe, S, P)
    for item in ['moisture', 'fe', 's', 'p']:
        actual = actual_values.get(item)
        coa = coa_values.get(item)
        if actual is not None and coa is not None:
            if actual > coa:
                final_status = "불합격"
                remarks.append(f"{component_labels.get(item, item)} 데이터 신뢰성 위반")

    final_remark = ", ".join(remarks) if remarks else "정상"
    
    new_record_data = {
        '날짜': [date.strftime('%Y-%m-%d')], 
        '공급사명': [supplier], 
        'Lot No': [lot_no], 
        '수량': [quantity], 
        **{f'coa_{k}': [v] for k, v in coa_values.items()}, 
        **{f'actual_{k}': [v] for k, v in actual_values.items()},
        '판정': [final_status], 
        '비고': [final_remark]
    }
    
    # DataFrame 생성 시 컬럼 순서를 COLUMNS 리스트에 맞게 지정
    df_new = pd.DataFrame(new_record_data, columns=COLUMNS)
    
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')
    
    return {'status': final_status, 'remark': final_remark, 'quantity': quantity}

# --- 5. 데이터 조회 및 SRM 분석 함수 (3-Strike Rule 구현) ---
def get_supplier_risk_and_stage(supplier):
    """공급사의 '연속' 불량 이력을 추적하여 SRM 단계와 조치를 반환합니다."""
    df = load_or_create_db()
    s_history = df[df['공급사명'] == supplier].sort_values(by='날짜', ascending=False)
    
    if s_history.empty or s_history.iloc[0]['판정'] == '합격':
        return {'stage': 0, 'status': '안전(Safe)', 'action': '정상 거래'}

    # 연속 불량 횟수 카운트
    consecutive_failures = 0
    for index, row in s_history.iterrows():
        if row['판정'] == '불합격':
            consecutive_failures += 1
        else:
            break # 합격 이력이 나오면 중단

    if consecutive_failures >= 3:
        return {'stage': 3, 'status': '비상(Critical)', 'action': 'New Business Hold (신규 수주 금지 및 거래 중단)'}
    elif consecutive_failures == 2:
        return {'stage': 2, 'status': '경고(Warning)', 'action': '현장 실사(Audit) 통보 및 페널티 부여'}
    elif consecutive_failures == 1:
        return {'stage': 1, 'status': '주의(Caution)', 'action': 'SCAR(시정조치요구서) 발송'}
    
    return {'stage': 0, 'status': '안전(Safe)', 'action': '정상 거래'} # 이론상 도달하지 않음

def generate_action_email(supplier, lot_no, stage, details):
    """SRM 단계(Stage)에 따라 각기 다른 AI 메일/보고서를 생성합니다."""
    if not client: return "OpenAI API 키가 설정되지 않았습니다."

    prompts = {
        1: {
            "recipient": f"{supplier} 담당자",
            "title": f"품질 불량 관련 시정조치요구서(SCAR) 발행 건 (Lot No: {lot_no})",
            "body": f"상세 내용:\n{details}\n\n상기 Lot에 대한 즉각적인 반품 조치 및 원인 분석 보고서(5-Why 등) 제출을 요청합니다."
        },
        2: {
            "recipient": f"{supplier} 품질팀장",
            "title": f"[긴급] 반복적인 품질 불량 발생 및 현장 실사 통보 건 (Lot No: {lot_no})",
            "body": f"상세 내용:\n{details}\n\n동일 유형의 품질 문제가 재발함에 따라, 귀사 공급망 관리 시스템에 대한 심각한 우려를 표합니다. 2주 내 당사 품질팀의 현장 실사가 있을 예정임을 공식 통보합니다. 관련 페널티가 부과될 수 있습니다."
        },
        3: {
            "recipient": "내부 경영진",
            "title": f"공급사 '{supplier}'에 대한 거래 중단(Stop Deal) 심의 안건",
            "body": f"상세 내용:\n{details}\n\n해당 공급사는 3회 연속 중대 품질 문제를 야기하여 공급망에 심각한 리스크를 초래하고 있습니다. 이에 따라, '{supplier}'를 부적격 공급사로 지정하고 모든 신규 발주를 중단하는 'New Business Hold' 조치를 즉시 시행할 것을 제안합니다. 차주 SCM 위원회 안건으로 상정 바랍니다."
        }
    }
    
    if stage not in prompts: return "잘못된 단계입니다."
    
    info = prompts[stage]
    prompt = f"수신자: {info['recipient']}\n제목: {info['title']}\n\n위 정보를 바탕으로, 매우 전문적이고 상황에 맞는 공식적인 톤앤매너의 문서(이메일 또는 보고서)를 한국어로 작성해줘. 내용은 아래와 같아.\n\n{info['body']}"
    
    return client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

# --- 기존 데이터 조회 함수들 ---
def get_unique_suppliers():
    return load_or_create_db()['공급사명'].unique().tolist()

def get_records_by_supplier(supplier):
    return load_or_create_db()[load_or_create_db()['공급사명'] == supplier]

def get_records_by_date_range(start_date, end_date):
    df = load_or_create_db()
    df['날짜'] = pd.to_datetime(df['날짜'])
    return df[(df['날짜'] >= pd.to_datetime(start_date)) & (df['날짜'] <= pd.to_datetime(end_date))]

def generate_inbound_approval_message(supplier, lot_no, assessment_result):
    """품질 검사 결과에 따라 입고 승인 메시지를 생성하거나 입고 보류를 알립니다."""
    if assessment_result['status'] == '합격':
        if not client:
            return "⚠️ OpenAI API 키가 설정되지 않아 AI 메시지 생성을 건너뛰고 기본 메시지를 반환합니다.\n✅ [입고 승인] 공급처: {supplier} (LOT: {lot_no}) 품질 검사 합격. 물류/창고 담당자는 전산상 입고 처리를 진행해 주시기 바랍니다."

        prompt = f"공급처 '{supplier}'의 LOT 번호 '{lot_no}'에 대한 품질 검사가 '합격'으로 최종 판정되었습니다. 물류 및 창고 담당자가 해당 LOT에 대해 즉시 전산상 '입고(Inbound)' 처리를 진행하도록, 명확하고 친절한 알림 메시지를 이모지를 사용하여 작성해주세요."
        
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant creating clear, friendly, and actionable notifications for a warehouse management system."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            # OpenAI API 호출 실패 시 대체 메시지
            return f"⚠️ GPT-4o 호출 중 오류 발생: {e}\n✅ [입고 승인] 공급처: {supplier} (LOT: {lot_no}) 품질 검사 합격. 물류/창고 담당자는 전산상 입고 처리를 진행해 주시기 바랍니다."
    else:
        return "⛔ [입고 보류] 품질 부적합 판정으로 입고 불가"