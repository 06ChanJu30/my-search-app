import re
import json
import os
import fitz
import gdown  # [V24] gdown 임포트

# [V24] AI 검색 모듈 임포트
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
except ImportError:
    print("="*50)
    print("!!! 필수 모듈 오류 !!!")
    print("AI 검색에 필요한 'sentence-transformers' 또는 'faiss-cpu'가 없습니다.")
    print("터미널에 아래 명령어를 입력해서 설치해주세요.")
    print("pip install sentence-transformers faiss-cpu")
    print("="*50)
    exit()

# --- 설정 ---
# [V24] 1단계에서 복사한 Google 드라이브 공유 링크를 여기에 붙여넣으세요!
GOOGLE_DRIVE_URL = "https://drive.google.com/file/d/1HSsJwmN2TRQOGXSL2Jqr2suRyeqkfT1w/view?usp=sharing"
PDF_FILE_NAME = "standard.pdf" # 다운로드 후 저장될 파일 이름
OUTPUT_JSON_NAME = "standards_data.json"
OUTPUT_INDEX_NAME = "toc.index"
# ---

# [V21] PDF 목차(2~4p)에 'page_start'와 'page_end'를 정확하게 적용
MANUAL_TOC_DATA = [
    {"id": "가설-01", "title": "가설사무실 안전기준", "page_start": 5, "page_end": 6},
    {"id": "가설-02", "title": "컨테이너 반입 프로세스", "page_start": 7, "page_end": 7},
    {"id": "가설-03", "title": "난방기 사용기준", "page_start": 8, "page_end": 9},
    {"id": "가설-04", "title": "화장실/휴게실/복리후생시설 설치기준", "page_start": 10, "page_end": 12},
    {"id": "가설전기-01", "title": "가설전선 사용기준", "page_start": 13, "page_end": 17},
    {"id": "작업장-01", "title": "SHOP장 관리기준", "page_start": 18, "page_end": 19},
    {"id": "작업장-02", "title": "공구함 관리기준", "page_start": 20, "page_end": 21},
    {"id": "PPE-01", "title": "업무별 복장 컬러코딩", "page_start": 22, "page_end": 23},
    {"id": "PPE-02", "title": "안전벨트/안전블럭", "page_start": 24, "page_end": 27},
    {"id": "PPE-03", "title": "호흡보호구 사용기준", "page_start": 28, "page_end": 29},
    {"id": "공도구-01", "title": "공도구 사용/점검 기준", "page_start": 30, "page_end": 32},
    {"id": "공도구-02", "title": "공도구별 안전기준/사고사례", "page_start": 33, "page_end": 37},
    {"id": "공도구-03", "title": "배터리 관리", "page_start": 38, "page_end": 39},
    {"id": "작업발판-01", "title": "사다리 사용기준", "page_start": 40, "page_end": 42},
    {"id": "작업발판-02", "title": "말비계", "page_start": 43, "page_end": 44},
    {"id": "작업발판-03", "title": "이동식 틀비계", "page_start": 45, "page_end": 46},
    {"id": "비계-01", "title": "비계설치계획서 작성기준", "page_start": 47, "page_end": 48},
    {"id": "비계-02", "title": "강관/시스템비계의 설치기준", "page_start": 49, "page_end": 51},
    {"id": "추락안전시설-01", "title": "개구부 방호 및 안전기준", "page_start": 52, "page_end": 53},
    {"id": "추락안전시설-02", "title": "안전난간 설치 기준", "page_start": 54, "page_end": 55},
    {"id": "추락안전시설-03", "title": "생명줄 설치 기준", "page_start": 56, "page_end": 57},
    {"id": "추락안전시설-04", "title": "안전시설 해체/설치 복구기준", "page_start": 58, "page_end": 59},
    {"id": "화재/폭발/질식-01", "title": "화기작업 공통기준", "page_start": 60, "page_end": 61},
    {"id": "화재/폭발/질식-02", "title": "화재감시자 자격인증제", "page_start": 62, "page_end": 63},
    {"id": "화재/폭발/질식-03", "title": "특정 고압가스 관리기준", "page_start": 64, "page_end": 65},
    {"id": "화재/폭발/질식-04", "title": "위험물 저장소 설치 & 관리기준", "page_start": 66, "page_end": 67},
    {"id": "화재/폭발/질식-05", "title": "열풍기 사용기준", "page_start": 68, "page_end": 69},
    {"id": "화재/폭발/질식-06", "title": "밀폐공간 안전기준", "page_start": 70, "page_end": 71},
    {"id": "차량계하역운반-01", "title": "자재 반입/반출 시 안전 Guide", "page_start": 72, "page_end": 74},
    {"id": "차량계하역운반-02", "title": "자재 하역/상차시 안전기준", "page_start": 75, "page_end": 77},
    {"id": "차량계하역운반-03", "title": "지게차 안전장치 및 상하차 안전", "page_start": 78, "page_end": 80},
    {"id": "차량계하역운반-04", "title": "굴착기 양중시 안전기준 / 고소작업대 관리 기준", "page_start": 81, "page_end": 82},
    {"id": "양중-01", "title": "양중작업계획서 작성", "page_start": 83, "page_end": 85},
    {"id": "양중-02", "title": "와이어, 웹벨트, 셔클 등 관리기준", "page_start": 86, "page_end": 90},
    {"id": "양중-03", "title": "체인블럭/레버블럭", "page_start": 91, "page_end": 93},
    {"id": "양중-04", "title": "양중함 및 톤백의 안전", "page_start": 94, "page_end": 97},
    {"id": "양중-05", "title": "윈치 및 호이스트 사용기준 / 신호수/유도원", "page_start": 98, "page_end": 99},
    {"id": "MSDS-01", "title": "물질안전보건 일반", "page_start": 100, "page_end": 103}
]

def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[\s\W_]+', '', text)
    return text

def create_database(data_list, pdf_path):
    
    if not os.path.exists(pdf_path):
        print(f"!!! '{pdf_path}' 파일을 찾을 수 없습니다.")
        return

    doc = fitz.open(pdf_path)
    processed_data = []
    texts_to_embed = []
    
    print("1. JSON 데이터베이스 및 AI 검색용 텍스트 추출 중...")
    for item in data_list:
        page_content = ""
        try:
            for page_num in range(item["page_start"], item["page_end"] + 1):
                if page_num > 4: 
                    page = doc.load_page(page_num - 1)
                    page_content += page.get_text("text") + " "
        except Exception as e:
            print(f"경고: {item['id']}의 페이지({item['page_start']}) 읽기 실패: {e}")
            
        full_text_blob = item["id"] + " " + item["title"] + " " + page_content
        
        item["search_normalized"] = normalize_text(full_text_blob)
        processed_data.append(item)
        texts_to_embed.append(full_text_blob)
    
    doc.close()

    with open(OUTPUT_JSON_NAME, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=4)
    print(f"-> '{OUTPUT_JSON_NAME}' 생성 완료 ({len(processed_data)}개 항목)")

    print("2. AI 검색 인덱스 생성 중... (모델 다운로드 포함, 1~2분 소요)")
    try:
        model = SentenceTransformer('jhgan/ko-sroberta-multitask')
        embeddings = model.encode(texts_to_embed, show_progress_bar=True)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(np.array(embeddings).astype('float32'))
        faiss.write_index(index, OUTPUT_INDEX_NAME)
        print(f"-> '{OUTPUT_INDEX_NAME}' 생성 완료!")
    except Exception as e:
        print(f"!!! AI 인덱스 생성 실패: {e}")

if __name__ == "__main__":
    # [V24] 실행 시 PDF 다운로드
    if GOOGLE_DRIVE_URL == "여기에_구글_드라이브_공유_링크_붙여넣기":
        print("="*50)
        print("!!! 오류: 'data_builder.py' 파일 20번째 줄의")
        print("GOOGLE_DRIVE_URL 변수에 Google 드라이브 링크를 입력하세요.")
        print("="*50)
    else:
        print(f"Google 드라이브에서 '{PDF_FILE_NAME}' 다운로드 중...")
        gdown.download(GOOGLE_DRIVE_URL, PDF_FILE_NAME, quiet=False, fuzzy=True)
        print("다운로드 완료. 데이터베이스 생성을 시작합니다.")
        create_database(MANUAL_TOC_DATA, PDF_FILE_NAME)