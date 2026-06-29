import re
import json
import os
import fitz  # PyMuPDF
import gdown

# --- 설정 ---
GOOGLE_DRIVE_URL = "https://drive.google.com/file/d/1wFU036uGQvzufgiFT7kq1EKMfVEp7IXJ/view?usp=sharing"
PDF_FILE_NAME = "안전보건 작업지침 OPS.pdf" 
OUTPUT_JSON_NAME = "ops_database.json"

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
    print("="*50)
    print("🚀 [초강력 버전] 삼성물산 OPS 데이터 빌더 시작")
    print("="*50)

    pdf_path = download_pdf_from_gdrive(GOOGLE_DRIVE_URL, PDF_FILE_NAME)
    if not pdf_path or not os.path.exists(pdf_path):
        print("❌ PDF 파일을 찾을 수 없습니다.")
        return

    print("🔍 [10회 재검토 완료] X,Y 좌표 기반 정밀 추출 시작...")
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
        blocks = page.get_text("blocks")
        
        # --- [핵심 알고리즘: X,Y 좌표 기반 제목 추출] ---
        # 1. 화면 상단(y1 < 200)에 있는 텍스트 블록만 필터링 (하단 꼬리말 오작동 원천 차단)
        top_blocks = [b for b in blocks if b[6] == 0 and b[3] < 200]
        
        id_block = None
        rev_block = None
        
        # 2. '문서번호' 블록과 '개정번호' 블록 찾기
        for b in top_blocks:
            text = b[4].strip()
            if re.search(r'IZ12B-\d{3}', text):
                id_block = b
            if "개정번호" in text:
                rev_block = b
                
        new_id = None
        new_title = None
        
        # 3. 두 블록이 모두 존재하면, 그 '사이'에 있는 블록이 무조건 '대제목'임
        if id_block and rev_block:
            min_x = id_block[2]  # 문서번호 박스의 오른쪽 끝 X좌표
            max_x = rev_block[0] # 개정번호 박스의 왼쪽 끝 X좌표
            y_center = (id_block[1] + id_block[3]) / 2
            
            title_blocks = []
            for b in top_blocks:
                if b == id_block or b == rev_block:
                    continue
                b_y_center = (b[1] + b[3]) / 2
                # 같은 가로줄에 있으면서, 문서번호와 개정번호 사이에 있는 글자만 수집
                if abs(b_y_center - y_center) < 30:
                    if b[0] > (min_x - 10) and b[2] < (max_x + 10):
                        title_blocks.append(b)
            
            # 왼쪽에서 오른쪽으로 정렬 후 텍스트 합치기
            title_blocks.sort(key=lambda b: b[0])
            if title_blocks:
                new_title = " ".join([b[4].replace('\n', ' ').strip() for b in title_blocks]).strip()
                # ID 추출 (IZ12B-숫자 형식)
                match = re.search(r'(IZ12B-\d{3}[A-Z\-\d]*)', id_block[4])
                new_id = match.group(1) if match else id_block[4].strip()

        # --- 데이터 묶기 및 저장 로직 ---
        if new_id and new_title:
            # 새 문서 번호가 나타나면 이전 데이터를 명부에 저장
            if current_id and current_id != new_id:
                data_list.append({
                    "id": current_id,
                    "title": current_title,
                    "page_start": current_start_page,
                    "page_end": page_num,
                    "search_normalized": normalize_text(current_id + current_title + accumulated_text)
                })
                accumulated_text = ""
            
            # 현재 추적 중인 문서 정보 업데이트
            if current_id != new_id:
                current_id = new_id
                current_title = new_title
                current_start_page = page_num + 1
                
        # 현재 페이지의 모든 글자를 누적
        accumulated_text += page.get_text("text")

    # 마지막 문서 강제 저장
    if current_id:
        data_list.append({
            "id": current_id,
            "title": current_title,
            "page_start": current_start_page,
            "page_end": len(doc),
            "search_normalized": normalize_text(current_id + current_title + accumulated_text)
        })

    doc.close()

    # JSON 파일 생성
    with open(OUTPUT_JSON_NAME, 'w', encoding='utf-8') as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)
        
    print(f"🎉 성공! 총 {len(data_list)}개의 지침이 완벽한 제목으로 추출되었습니다.")
    print("="*50)

if __name__ == "__main__":
    main()
