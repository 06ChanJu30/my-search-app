import re
import json
import os
import fitz
import gdown

# [V25] AI 검색 모듈 임포트
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
# [수정됨] 사용자가 제공한 새 Google 드라이브 링크 반영
GOOGLE_DRIVE_URL = "https://drive.google.com/file/d/1wFU036uGQvzufgiFT7kq1EKMfVEp7IXJ/view?usp=sharing"
PDF_FILE_NAME = "standard.pdf" 
OUTPUT_JSON_NAME = "standards_data.json"
OUTPUT_INDEX_NAME = "toc.index"
# ---

# [V25] 2025.11.06 (Rev.01) 새 PDF 목차 기준 (페이지 밀림 반영)
MANUAL_TOC_DATA = [
    {"id": "가설-01", "title": "가설사무실 안전기준", "page_start": 7, "page_end": 8}, # 5->7
    {"id": "가설-02", "title": "컨테이너 반입 프로세스", "page_start": 9, "page_end": 9}, # 7->9
    {"id": "가설-03", "title": "난방기 사용기준", "page_start": 10, "page_end": 11}, # 8->10
    {"id": "가설-04", "title": "화장실/휴게실/복리후생시설 설치기준", "page_start": 12, "page_end": 14}, # 10->12
    {"id": "가설전기-01", "title": "가설전선 사용기준", "page_start": 15, "page_end": 19}, # 13->15
    {"id": "작업장-01", "title": "SHOP장 관리기준", "page_start": 20, "page_end": 21}, # 18->20
    {"id": "작업장-02", "title": "공구함 관리기준", "page_start": 22, "page_end": 23}, # 20->22
    {"id": "PPE-01", "title": "업무별 복장 컬러코딩", "page_start": 24, "page_end": 25}, # 22->24
    {"id": "PPE-02", "title": "안전벨트/안전블럭", "page_start": 26, "page_end": 29}, # 24->26
    {"id": "PPE-03", "title": "호흡보호구 사용기준", "page_start": 30, "page_end": 31}, # 28->30
    {"id": "공도구-01", "title": "공도구 사용/점검 기준", "page_start": 32, "page_end": 34}, # 30->32
    {"id": "공도구-02", "title": "공도구별 안전기준/사고사례", "page_start": 35, "page_end": 39}, # 33->35
    {"id": "공도구-03", "title": "배터리 관리", "page_start": 40, "page_end": 41}, # 38->40
    {"id": "작업발판-01", "title": "사다리 사용기준", "page_start": 42, "page_end": 44}, # 40->42
    {"id": "작업발판-02", "title": "말비계", "page_start": 45, "page_end": 46}, # 43->45
    {"id": "작업발판-03", "title": "이동식 틀비계", "page_start": 47, "page_end": 48}, # 45->47
    {"id": "비계-01", "title": "비계설치계획서 작성기준", "page_start": 49, "page_end": 50}, # 47->49
    {"id": "비계-02", "title": "강관/시스템비계의 설치기준", "page_start": 51, "page_end": 53}, # 49->51
    {"id": "추락안전시설-01", "title": "개구부 방호 및 안전기준", "page_start": 54, "page_end": 55}, # 52->54
    {"id": "추락안전시설-02", "title": "안전난간 설치 기준", "page_start": 56, "page_end": 57}, # 54->56
    {"id": "추락안전시설-03", "title": "생명줄 설치 기준", "page_start": 58, "page_end": 59}, # 56->58
    {"id": "추락안전시설-04", "title": "안전시설 해체/설치 복구기준", "page_start": 60, "page_end": 61}, # 58->60
    {"id": "화재/폭발/질식-01", "title": "화기작업 공통기준", "page_start": 62, "page_end": 63}, # 60->62
    {"id": "화재/폭발/질식-02", "title": "화재감시자 자격인증제", "page_start": 64, "page_end": 65}, # 62->64
    {"id": "화재/폭발/질식-03", "title": "특정 고압가스 관리기준", "page_start": 66, "page_end": 67}, # 64->66
    {"id": "화재/폭발/질식-04", "title": "위험물 저장소 설치 & 관리기준", "page_start": 68, "page_end": 69}, # 66->68
    {"id": "화재/폭발/질식-05", "title": "열풍기 사용기준", "page_start": 70, "page_end": 71}, # 68->70
    {"id": "화재/폭발/질식-06", "title": "밀폐공간 안전기준", "page_start": 72, "page_end": 73}, # 70->72
    {"id": "차량계하역운반-01", "title": "자재 반입/반출 시 안전 Guide", "page_start": 74, "page_end": 76}, # 72->74
    {"id": "차량계하역운반-02", "title": "자재 하역/상차시 안전기준", "page_start": 77, "page_end": 79}, # 75->77
    {"id": "차량계하역운반-03", "title": "지게차 안전장치 및 상하차 안전", "page_start": 80, "page_end": 82}, # 78->80
    {"id": "차량계하역운반-04", "title": "굴착기 양중시 안전기준 / 고소작업대 관리 기준", "page_start": 83, "page_end": 84}, # 81->83
    {"id": "양중-01", "title": "양중작업계획서 작성", "page_start": 85, "page_end": 87}, # 83->85
    {"id": "양중-02", "title": "와이어, 웹벨트, 셔클 등 관리기준", "page_start": 88, "page_end": 92}, # 86->88
    {"id": "양중-03", "title": "체인블럭/레버블럭", "page_start": 93, "page_end": 95}, # 91->93
    {"id": "양중-04", "title": "양중함 및 톤백의 안전", "page_start": 96, "page_end": 99}, # 94->96
    {"id": "K-05-①", "title": "고소작업대", "page_start": 101, "page_end": 101}, 
    {"id": "K-05-②", "title": "신호수/유도원", "page_start": 101, "page_end": 101},
    {"id": "MSDS-01", "title": "물질안전보건 일반", "page_start": 102, "page_end": 105} # 100->102
]


def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[\s\W_]+', '', text)
    return text

def create_database(data_list, pdf_path):
    """[V25] JSON과 FAISS 인덱스를 생성합니다."""
    
    if not os.path.exists(pdf_path):
        print(f"!!! '{pdf_path}' 파일을 찾을 수 없습니다. G-Drive 다운로드가 실패했을 수 있습니다.")
        return

    doc = fitz.open(pdf_path)
    processed_data = []
    texts_to_embed = []
    
    print("1. JSON 데이터베이스 및 AI 검색용 텍스트 추출 중...")
    for item in data_list:
        page_content = ""
        try:
            # 목차 페이지(3~6p) 제외하고 본문 추출
            for page_num in range(item["page_start"], item["page_end"] + 1):
                if page_num > 6: 
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
    print(f"Google 드라이브에서 '{PDF_FILE_NAME}' 다운로드 중...")
    gdown.download(GOOGLE_DRIVE_URL, PDF_FILE_NAME, quiet=False, fuzzy=True)
    print("다운로드 완료. 데이터베이스 생성을 시작합니다.")
    create_database(MANUAL_TOC_DATA, PDF_FILE_NAME)
