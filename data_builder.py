import re
import json
import os
import fitz  # PyMuPDF
import gdown

# --- 설정 ---
GOOGLE_DRIVE_URL = "https://drive.google.com/file/d/1wFU036uGQvzufgiFT7kq1EKMfVEp7IXJ/view?usp=sharing"
PDF_FILE_NAME = "안전보건 작업지침 OPS.pdf" 
OUTPUT_JSON_NAME = "ops_database.json"

# --- 함수 정의 ---
def normalize_text(text):
    text = str(text).lower()
    text = re.sub(r'[\s\W_]+', '', text)
    return text

def download_pdf_from_gdrive(url, output_path):
    if os.path.exists(output_path):
        print(f"✅ 이미 PDF 파일이 존재합니다: {output_path}")
        return output_path
    try:
        print(f"📥 구글 드라이브에서 PDF 다운로드 시작...")
        gdown.download(url, output_path, quiet=False, fuzzy=True)
        return output_path
    except Exception as e:
        print(f"⚠️ PDF 다운로드 실패: {e}")
        return None

def main():
    print("="*40)
    print("🚀 삼성물산 OPS 데이터 빌더 시작")
    print("="*40)

    # 1. PDF 다운로드 (또는 기존 파일 읽기)
    pdf_path = download_pdf_from_gdrive(GOOGLE_DRIVE_URL, PDF_FILE_NAME)
    if not pdf_path or not os.path.exists(pdf_path):
        print("❌ PDF 파일을 찾을 수 없어 추출을 종료합니다.")
        return

    # 2. 🌟 강력한 데이터 추출 로직 🌟
    print("🔍 PDF에서 정확한 제목과 데이터를 추출합니다...")
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"❌ PDF 열기 실패: {e}")
        return

    data_list = []
    current_id = None
    current_title = None
    current_start_page = 0
    accumulated_text = ""

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        
        # [핵심] 정규식을 사용하여 "IZ12B-숫자" 패턴과 그 옆의 "대제목"을 정확히 찾아냅니다.
        # 예: IZ12B-217      모듈화 장비(2) 스트랜드잭      개정번호
        match = re.search(r'(IZ12B-\d{3}[A-Z\-\d]*)\s+(.*?)\s+개정번호', text)
        
        if match:
            new_id = match.group(1).strip()
            new_title = match.group(2).strip()
            
            # 문서 번호가 바뀌면 (새로운 지침이 시작되면), 지금까지 모은 데이터를 저장합니다.
            if current_id and current_id != new_id:
                data_list.append({
                    "id": current_id,
                    "title": current_title,
                    "page_start": current_start_page,
                    "page_end": page_num, # 이전 페이지까지
                    "search_normalized": normalize_text(current_id + current_title + accumulated_text)
                })
                accumulated_text = "" # 텍스트 초기화
                
            # 새로운 지침 정보로 업데이트
            if current_id != new_id:
                current_id = new_id
                current_title = new_title
                current_start_page = page_num + 1 # 사용자에게 보여줄 때는 1페이지부터 시작
                
        # 현재 페이지의 모든 글자를 검색용 데이터에 누적시킵니다.
        accumulated_text += text

    # 마지막 문서 처리
    if current_id:
        data_list.append({
            "id": current_id,
            "title": current_title,
            "page_start": current_start_page,
            "page_end": len(doc),
            "search_normalized": normalize_text(current_id + current_title + accumulated_text)
        })

    doc.close()

    # 3. JSON 파일로 저장
    with open(OUTPUT_JSON_NAME, 'w', encoding='utf-8') as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)
        
    print(f"🎉 성공! 총 {len(data_list)}개의 지침이 완벽한 제목으로 '{OUTPUT_JSON_NAME}'에 저장되었습니다!")
    print("="*40)

if __name__ == "__main__":
    main()
