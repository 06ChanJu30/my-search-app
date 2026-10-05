import streamlit as st
import pandas as pd
import json
import os
import re
import fitz  # PyMuPDF
import datetime
import csv
import uuid
import requests
import base64
import time

# ---------------------------------------------------------
# 1. 페이지 설정 및 네비게이션 변수 고정 (오타 원천 차단)
# ---------------------------------------------------------
st.set_page_config(page_title="작업지침 OPS 검색기", layout="centered", initial_sidebar_state="collapsed")

MENU_SEARCH = "🔍 지침 검색"
MENU_ADMIN = "⚙️ 관리자 대시보드"
menu = st.sidebar.radio("메뉴 이동", [MENU_SEARCH, MENU_ADMIN])

# ---------------------------------------------------------
# 2. 리소스 및 디렉토리 설정
# ---------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(current_dir, "ops_database.json")
if not os.path.exists(JSON_FILE_PATH):
    JSON_FILE_PATH = os.path.join(current_dir, "standards_data.json")
    
PDF_FILE_PATH = os.path.join(current_dir, "안전보건 작업지침 OPS.pdf") 
VECTOR_INDEX_PATH = os.path.join(current_dir, "vector_db.index")
LOG_FILE_PATH = os.path.join(current_dir, "search_logs.csv")

# ---------------------------------------------------------
# 3. 데이터 및 AI 모델 캐싱 로드
# ---------------------------------------------------------
@st.cache_data(show_spinner="데이터베이스(JSON)를 메모리에 로딩 중입니다...")
def load_ops_data():
    if not os.path.exists(JSON_FILE_PATH):
        return pd.DataFrame()
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            df = df[~df['title'].str.contains('개정이력|목차', case=False, na=False)]
            
            if 'search_normalized' not in df.columns:
                df['search_normalized'] = ""
            if 'title' not in df.columns:
                df['title'] = "제목없음"
                
            def assign_major_category(row):
                text = str(row.get('title', '')) + str(row.get('category', '')) + str(row.get('id', ''))
                if 'IZ12B-1' in text: return '1. 공통'
                elif 'IZ12B-2' in text: return '2. 장비'
                elif 'IZ12B-3' in text: return '3. 보건'
                elif 'IZ12B-4' in text: return '4. 건축'
                elif 'IZ12B-5' in text: return '5. 토목'
                elif 'IZ12B-6' in text: return '6. ES'
                elif 'IZ12B-7' in text: return '7. 하이테크'
                
                if any(k in text for k in ['보호구', '공도구', '철근', '거푸집', '동바리', '화기작업', '콘크리트', '비계', '추락', '낙하', '전기', '하역', '운반', '화재', '가설', '안전벨트', '생명줄', '난간']): return '1. 공통'
                elif any(k in text for k in ['크레인', '리프트', '곤돌라', '고소작업', '지게차', '굴착기', '토공장비', '항타', '천공기', '타설장비', '해상장비', '특수장비', '줄걸이', '사다리차', '압축기', '압력용기', '모듈화장비', '로봇', '양중']): return '2. 장비'
                elif any(k in text for k in ['밀폐공간', '방사선', '유해위험물질', '질식', 'MSDS', '보건']): return '3. 보건'
                elif any(k in text for k in ['철골', '해체', '철거', '습식', '외장', '내장', 'PC', '도장', '방수', '조경', '엘리베이터', '에스컬레이터', '건축']): return '4. 건축'
                elif any(k in text for k in ['토공', '벌목', '발파', '항타작업', '터널', '교량', '댐', '흙막이', '포장', '항만', '토목']): return '5. 토목'
                elif any(k in text for k in ['시운전', 'LOTO', '원자로', '보일러', '철탑', 'LNG', '태양광']): return '6. ES'
                elif any(k in text for k in ['배관', '모듈화시공', '천장', '하이테크']): return '7. 하이테크'
                else: return '1. 공통'
                
            df['major_category'] = df.apply(assign_major_category, axis=1)
            df['clean_title'] = df['title'].str.replace(r'[^가-힣a-zA-Z0-9]', '', regex=True)
            df = df.drop_duplicates(subset=['clean_title'], keep='first')
            if 'id' not in df.columns: 
                df['id'] = df.index.astype(str)
            
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_resource(show_spinner="원본 PDF 매뉴얼을 로딩 중입니다...")
def load_pdf_bytes():
    if os.path.exists(PDF_FILE_PATH):
        with open(PDF_FILE_PATH, "rb") as f: return f.read()
    return None

@st.cache_resource(show_spinner="AI 추천 엔진을 로딩 중입니다...")
def load_ai_models():
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
        model = SentenceTransformer("snunlp/KR-SBERT-V40K-klueNLI-augSTS")
        index = faiss.read_index(VECTOR_INDEX_PATH) if os.path.exists(VECTOR_INDEX_PATH) else None
        return model, index
    except Exception:
        return None, None

df = load_ops_data()
pdf_bytes = load_pdf_bytes()
ai_model, faiss_index = load_ai_models()

# ---------------------------------------------------------
# 백그라운드 영구 로깅 (GitHub API 연동 - 동시성 충돌 방지 로직 적용)
# ---------------------------------------------------------
def log_search(query, result_count):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{now},{query},{result_count}\n"
    
    try:
        file_exists = os.path.exists(LOG_FILE_PATH)
        with open(LOG_FILE_PATH, "a", newline="", encoding="utf-8-sig") as f:
            if not file_exists:
                f.write("Timestamp,Search_Query,Result_Count\n")
            f.write(log_line)
    except Exception:
        pass
        
    if "GITHUB_TOKEN" in st.secrets and "REPO_NAME" in st.secrets:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        url = f"https://api.github.com/repos/{repo}/contents/search_logs.csv"
        headers = {"Authorization": f"token {token}"}
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                res = requests.get(url, headers=headers)
                if res.status_code == 200:
                    file_data = res.json()
                    sha = file_data['sha']
                    content = base64.b64decode(file_data['content']).decode('utf-8')
                    new_content = content + log_line
                else:
                    sha = None
                    new_content = "Timestamp,Search_Query,Result_Count\n" + log_line
                    
                payload = {
                    "message": f"Auto-log: search '{query}'",
                    "content": base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
                }
                if sha: payload["sha"] = sha
                
                put_res = requests.put(url, headers=headers, json=payload)
                
                if put_res.status_code in [200, 201]:
                    break
                elif put_res.status_code == 409:
                    time.sleep(1)
                    continue
                else:
                    break
            except Exception:
                time.sleep(1)

@st.cache_data(show_spinner=False)
def convert_df_to_csv_for_vba(result_dataframe):
    export_df = result_dataframe.drop(columns=['search_normalized', 'clean_title', 'match_score', 'relevance_score'], errors='ignore').copy()
    export_df['Report_Date'] = datetime.datetime.now().strftime("%Y-%m-%d")
    export_df['Target_Cell_Width'] = 400
    export_df['Target_Cell_Height'] = 300
    return export_df.to_csv(index=False).encode('utf-8-sig')

# ---------------------------------------------------------
# 개인 AI API 접근 백도어 (Headless Mode)
# ---------------------------------------------------------
params = st.query_params
api_query = params.get("query")
api_format = params.get("format")

if api_format == "json" and api_query:
    keywords = api_query.strip().split()
    mask = pd.Series([True] * len(df), index=df.index)
    for kw in keywords:
        kw_mask = df['title'].str.lower().str.contains(kw.lower(), regex=False, na=False) | \
                  df['search_normalized'].str.lower().str.contains(kw.lower(), regex=False, na=False)
        mask = mask & kw_mask
        
    result_df = df[mask].copy()
    
    result_df['relevance_score'] = 0
    for kw in keywords:
        kw_lower = kw.lower()
        result_df.loc[result_df['title'].str.lower().str.contains(kw_lower, regex=False, na=False), 'relevance_score'] += 10
        result_df.loc[result_df['search_normalized'].str.lower().str.contains(kw_lower, regex=False, na=False), 'relevance_score'] += 1
    result_df = result_df.sort_values(by='relevance_score', ascending=False)
    
    log_search(api_query, len(result_df))
    
    response_data = {
        "status": "success",
        "query": api_query,
        "count": len(result_df),
        "results": result_df.drop(columns=['search_normalized', 'clean_title', 'relevance_score'], errors='ignore').to_dict(orient="records")
    }
    st.json(response_data)
    st.stop()

# ---------------------------------------------------------
# 4. 화면 렌더링 로직
# ---------------------------------------------------------
def display_manual_content(row, keywords=None, context_key=""):
    content_displayed = False
    
    if pdf_bytes is None:
        st.warning("원본 PDF 파일이 연결되어 있지 않습니다.")
        st.info(f"{row.get('answer', '내용없음')}")
        content_displayed = True
    else:
        local_pdf = fitz.open("pdf", pdf_bytes)
        try:
            if 'page_start' in row and pd.notna(row['page_start']) and row['page_start'] != "":
                try:
                    p_start = int(row['page_start'])
                    p_end = int(row.get('page_end', p_start))

                    for p in range(p_start, p_end + 1):
                        page_idx = p - 1
                        if 0 <= page_idx < len(local_pdf):
                            page = local_pdf[page_idx]
                            if keywords:
                                for kw in keywords:
                                    for inst in page.search_for(kw):
                                        page.add_highlight_annot(inst).update()
                                        
                            pix = page.get_pixmap(dpi=150)
                            st.image(pix.tobytes("png"), caption=f"원본 매뉴얼 (페이지 {p})", use_container_width=True)
                            if p != p_end: 
                                st.markdown("<br>", unsafe_allow_html=True)
                            content_displayed = True
                        else:
                            st.error(f"해당 페이지({p})를 PDF에서 찾을 수 없습니다.")
                except ValueError:
                    pass

            if not content_displayed:
                ref = row.get('reference', '')
                match = re.search(r'\(p\.(\d+)\)', ref)
                if match:
                    page_idx = int(match.group(1)) - 1
                    if 0 <= page_idx < len(local_pdf):
                        page = local_pdf[page_idx]
                        if keywords:
                            for kw in keywords:
                                for inst in page.search_for(kw):
                                    page.add_highlight_annot(inst).update()
                                    
                        pix = page.get_pixmap(dpi=150)
                        st.image(pix.tobytes("png"), caption=f"원본 매뉴얼 (페이지 {page_idx + 1})", use_container_width=True)
                        content_displayed = True
                    else:
                        st.error("해당 페이지를 PDF에서 찾을 수 없습니다.")
                else:
                    st.info(f"{row.get('answer', '내용없음')}")
                    content_displayed = True
        finally:
            local_pdf.close()
            
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        doc_id = row.get('id', row.get('title', 'unknown'))
        unique_btn_key = f"close_{doc_id}_{context_key}_{uuid.uuid4().hex[:8]}"
        if st.button("접기 (닫기) ⬆️", key=unique_btn_key, use_container_width=True):
            st.rerun()

# =========================================================
# 화면 분기: [1] 지침 검색 탭
# =========================================================
if menu == MENU_SEARCH:
    col1, col2 = st.columns([1.5, 8.5])
    with col1:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=120)
        else:
            st.markdown("<h1>💡</h1>", unsafe_allow_html=True)
    with col2:
        st.title("안전보건 작업지침 OPS")

    st.caption("개정된 삼성물산 7대 분류(공통, 장비, 보건, 건축, 토목, ES, 하이테크) 적용 완료")

    if st.button("🔄 최신 데이터 불러오기"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
        
    if df.empty:
        st.error("데이터베이스 파일이 없습니다. 깃허브에 JSON 데이터 파일을 업로드해주세요.")
        st.stop()
        
    default_search = api_query if api_query else ""
    query = st.text_input("🔍 검색어를 입력하세요. (예: 타워크레인, 고소작업대, 화기작업)", value=default_search)

    if query:
        keywords = query.strip().split()
        mask = pd.Series([True] * len(df), index=df.index)
        
        try:
            for kw in keywords:
                kw_lower = kw.lower()
                kw_mask = df['title'].str.lower().str.contains(kw_lower, regex=False, na=False) | \
                          df['search_normalized'].str.lower().str.contains(kw_lower, regex=False, na=False)
                mask = mask & kw_mask
                
            result_df = df[mask].copy()
            
            if query != api_query:
                log_search(query, len(result_df))
            
            if len(result_df) > 0:
                result_df['relevance_score'] = 0
                for kw in keywords:
                    kw_lower = kw.lower()
                    title_match = result_df['title'].str.lower().str.contains(kw_lower, regex=False, na=False)
                    result_df.loc[title_match, 'relevance_score'] += 10
                    content_match = result_df['search_normalized'].str.lower().str.contains(kw_lower, regex=False, na=False)
                    result_df.loc[content_match, 'relevance_score'] += 1
                
                result_df = result_df.sort_values(by='relevance_score', ascending=False)
                
                col_res1, col_res2 = st.columns([7, 3])
                with col_res1:
                    st.subheader(f"총 {len(result_df)}건의 검색 결과가 있습니다.")
                with col_res2:
                    st.download_button(
                        label="📥 엑셀용 데이터 다운로드",
                        data=convert_df_to_csv_for_vba(result_df),
                        file_name=f"ops_search_results_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                st.divider()
                for i, row in result_df.iterrows():
                    with st.expander(f"📖 [{row['major_category']}] {row.get('title', '제목없음')}"):
                        display_manual_content(row, keywords=keywords, context_key="main") 
            else:
                st.warning("정확히 일치하는 지침이 없습니다.")
            
            if len(result_df) <= 3:
                if ai_model and faiss_index:
                    st.info("💡 혹시 이런 지침을 찾으시나요? (AI 문맥 추천)")
                    import numpy as np
                    query_vector = ai_model.encode([query]).astype('float32')
                    distances, indices = faiss_index.search(query_vector, 10)
                    
                    valid_indices = []
                    for dist, idx in zip(distances[0], indices[0]):
                        if idx != -1 and idx in df.index:
                            if idx not in result_df.index:
                                valid_indices.append(idx)
                                
                    if valid_indices:
                        recommend_df = df.loc[valid_indices].head(5)
                        for i, row in recommend_df.iterrows():
                            with st.expander(f"✨(AI 추천) [{row['major_category']}] {row.get('title', '제목없음')}"):
                                display_manual_content(row, keywords=keywords, context_key="ai_rec")
                else:
                    df['match_score'] = 0 
                    for kw in keywords:
                        kw_lower = kw.lower()
                        df.loc[df['search_normalized'].str.lower().str.contains(kw_lower, regex=False, na=False), 'match_score'] += 1
                        df.loc[df['title'].str.lower().str.contains(kw_lower, regex=False, na=False), 'match_score'] += 2
                    
                    recommend_df = df[~df.index.isin(result_df.index)]
                    min_score_required = 1 if len(keywords) == 1 else 2
                    recommend_df = recommend_df[recommend_df['match_score'] >= min_score_required]
                    recommend_df = recommend_df.sort_values(by='match_score', ascending=False).head(5)
                    
                    if len(recommend_df) > 0:
                        st.info(f"💡 혹시 이런 지침을 찾으시나요? (연관성이 높은 지침 추천)")
                        for i, row in recommend_df.iterrows():
                            with st.expander(f"📖 [{row['major_category']}] {row.get('title', '제목없음')}"):
                                display_manual_content(row, keywords=keywords, context_key="txt_rec")

        except Exception as e:
            st.error(f"앗! 검색 중 문제가 발생했습니다: {e}")
            
    else:
        st.subheader("📑 분야별 작업지침 목차")
        categories = sorted(list(df['major_category'].unique()))
        selected_toc = st.selectbox("📂 조회할 카테고리를 선택하세요", ["(목차를 선택해주세요)"] + categories)
        
        if selected_toc != "(목차를 선택해주세요)":
            cat_df = df[df['major_category'] == selected_toc]
            for _, row in cat_df.iterrows():
                with st.expander(f"📖 {row.get('title', '제목없음')}"):
                    display_manual_content(row, context_key="toc") 

# =========================================================
# 화면 분기: [2] 관리자 대시보드
# =========================================================
elif menu == MENU_ADMIN:
    st.markdown("## ⚙️ 현장 검색 통계 및 DB 관리")
    
    admin_pw = st.secrets.get("ADMIN_PW", "admin1234")
    pwd = st.text_input("🔒 관리자 비밀번호를 입력하세요", type="password")
    
    if pwd == admin_pw:
        st.success("관리자 인증 완료")
        
        st.markdown("### 📊 누적 현장 검색 통계")
        if os.path.exists(LOG_FILE_PATH):
            log_df = pd.read_csv(LOG_FILE_PATH)
            if not log_df.empty:
                col_stat1, col_stat2 = st.columns(2)
                with col_stat1:
                    st.write("**🔥 가장 많이 검색된 키워드 (Top 5)**")
                    top_queries = log_df['Search_Query'].value_counts().head(5)
                    st.bar_chart(top_queries)
                with col_stat2:
                    st.write("**⚠️ 검색 실패 키워드 (결과 0건)**")
                    failed_searches = log_df[log_df['Result_Count'] == 0]['Search_Query'].value_counts().head(5)
                    if not failed_searches.empty:
                        st.bar_chart(failed_searches)
                    else:
                        st.info("검색 실패 기록이 없습니다.")
        else:
            st.info("아직 누적된 검색 로그가 없습니다.")
            
        st.divider()

        st.markdown("### 📑 신규 작업지침서(PDF) 업로드 및 DB 갱신")
        st.info("개정된 PDF를 업로드하면 서버에서 텍스트를 파싱하고 AI 인덱스를 갱신합니다.")
        
        uploaded_pdf = st.file_uploader("개정판 PDF 파일 선택", type="pdf")
        if uploaded_pdf:
            if st.button("🚀 DB 갱신 및 AI 학습 시작"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    status_text.text("진행 상태: [1/4] PDF 업로드 중...")
                    with open(PDF_FILE_PATH, "wb") as f:
                        f.write(uploaded_pdf.getbuffer())
                    progress_bar.progress(10)
                    
                    status_text.text("진행 상태: [2/4] PDF 텍스트 추출 중...")
                    new_doc = fitz.open(PDF_FILE_PATH)
                    new_data = []
                    texts_for_embedding = []
                    total_pages = len(new_doc)
                    
                    for i, page in enumerate(new_doc):
                        text = page.get_text("text").strip()
                        if text:
                            title_candidate = text.split('\n')[0]
                            row_dict = {
                                "id": f"NEW-{i}",
                                "title": title_candidate[:50],
                                "category": "신규업데이트",
                                "page_start": i + 1,
                                "page_end": i + 1,
                                "answer": text[:200]
                            }
                            new_data.append(row_dict)
                            texts_for_embedding.append(title_candidate + " " + text[:200])
                        
                        if total_pages > 0:
                            progress_bar.progress(10 + int((i / total_pages) * 40))
                            
                    new_doc.close()
                    
                    status_text.text("진행 상태: [3/4] JSON 데이터베이스 저장 중...")
                    with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
                        json.dump(new_data, f, ensure_ascii=False, indent=2)
                    progress_bar.progress(60)
                    
                    status_text.text("진행 상태: [4/4] AI 벡터 변환 및 인덱스 갱신 중...")
                    if ai_model:
                        import faiss
                        import numpy as np
                        new_embeddings = ai_model.encode(texts_for_embedding).astype('float32')
                        dimension = new_embeddings.shape[1]
                        new_index = faiss.IndexFlatL2(dimension)
                        new_index.add(new_embeddings)
                        faiss.write_index(new_index, VECTOR_INDEX_PATH)
                    progress_bar.progress(100)
                    
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    status_text.success("✅ 새로운 지침서 분석 및 벡터 DB 갱신 완료!")
                except Exception as e:
                    status_text.error(f"업데이트 중 오류 발생: {e}")
                    progress_bar.empty()
                    
    elif pwd:
        st.error("비밀번호가 일치하지 않습니다.")

# ---------------------------------------------------------
# 6. 하단 문의처
# ---------------------------------------------------------
st.divider()
st.caption("📄 문의: 안전팀 백찬주 대리 (010-2528-5706)")
