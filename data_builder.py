import re
import json
import os
import fitz  # PyMuPDF
import gdown
import time

# [V25] AI 검색 모듈 임포트
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
except ImportError:
    pass # 앱 실행 중에는 에러를 띄우지 않고 넘어갑니다.

# --- 설정 ---
GOOGLE_DRIVE_URL = "https://drive.google.com/file/d/1wFU036uGQvzufgiFT7kq1EKMfVEp7IXJ/view?usp=sharing"
PDF_FILE_NAME = "standard.pdf" 
OUTPUT_JSON_NAME = "standards_data.json"
OUTPUT_INDEX_NAME = "toc.index"

# --- 함수 정의 ---

def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[\s\W_]+', '', text)
    return text

def download_pdf_from_gdrive(url, output_path):
    if os.path.exists(output_path):
        print(f"이미 파일이 존재합니다: {output_path}")
        return output_path
    try:
        print(f"다운로드 시작: {output_path}")
        gdown.download(url, output_path, quiet=False, fuzzy=True)
        return output_path
    except Exception as e:
        print(f"PDF 다운로드 실패: {e}")
        return None

def main():
    """
    이 함수는 직접 실행할 때만 작동합니다.
    (스트림릿 앱이 이 파일을 import 해도 실행되지 않습니다.)
    """
    print("="*30)
    print("🚀 데이터 빌더 시작 (로컬 전용)")
    print("="*30)

    # 1. PDF 다운로드
    pdf_path = download_pdf_from_gdrive(GOOGLE_DRIVE_URL, PDF_FILE_NAME)
    if not pdf_path:
        return

    # 2. 데이터 추출 로직 (여기에 기존 로직 포함)
    # ... (기존에 작성하신 로직이 실행됩니다) ...
    # 주의: 이 파일은 로컬에서 데이터를 '만들 때'만 쓰세요.
    # 서버에는 standards_data.json과 toc.index만 있으면 됩니다.
    
    print("✅ 모든 작업 완료!")

# [핵심 수정] 이 부분이 있어야 import 할 때 자동 실행을 막습니다.
if __name__ == "__main__":
    main()
