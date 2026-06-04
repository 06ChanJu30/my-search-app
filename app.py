import streamlit as st
import pandas as pd
import json
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="작업지침 OPS 검색기", page_icon="💡", layout="centered")

st.title("💡 안전보건 작업지침 OPS 검색")
st.caption("현장 안전보건 작업지침(OPS) 단독 검색 엔진")

# 2. 오직 새 작업지침 데이터만 불러오기
current_dir = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(current_dir, "ops_database.json")

@st.cache_data
def load_ops_data():
    if not os.path.exists(JSON_FILE_PATH):
        return pd.DataFrame()
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return pd.DataFrame()

df = load_ops_data()

if df.empty:
    st.error("데이터베이스 파일(ops_database.json)을 찾을 수 없습니다. 깃허브에 파일이 잘 올라갔는지 확인해주세요.")
    st.stop()

# 3. 검색창 (다중 키워드 지원)
query = st.text_input("🔍 검색어를 띄어쓰기로 여러 개 입력해보세요. (예: 타워크레인 신호수, 화기작업 소화기)")

# 4. 검색 및 추천 로직
if query:
    keywords = query.strip().split()
    
    # 교집합(AND) 검색: 입력한 단어가 모두 포함된 지침 찾기
    mask = pd.Series([True] * len(df), index=df.index)
    for kw in keywords:
        kw_mask = df['question'].str.contains(kw, case=False, na=False) | \
                  df['answer'].str.contains(kw, case=False, na=False)
        mask = mask & kw_mask
        
    result_df = df[mask]
    
    st.subheader(f"총 {len(result_df)}건의 작업지침이 검색되었습니다.")
    st.divider()
    
    if len(result_df) == 0:
        st.warning("정확히 일치하는 지침이 없습니다.")
        
        # 합집합(OR) 유사 검색: 단어 중 하나라도 포함된 지침 추천
        or_mask = pd.Series([False] * len(df), index=df.index)
        for kw in keywords:
            kw_mask = df['question'].str.contains(kw, case=False, na=False) | \
                      df['answer'].str.contains(kw, case=False, na=False)
            or_mask = or_mask | kw_mask
        
        related_df = df[or_mask]
        
        if len(related_df) > 0:
            st.info(f"💡 혹시 이런 지침을 찾으시나요? (유사 결과 {len(related_df)}건 추천)")
            for i, row in related_df.head(10).iterrows():
                with st.expander(f"[{row.get('category', '분류없음')}] {row.get('title', '제목없음')}"):
                    st.info(f"**💡 안전 기준:**\n\n{row.get('answer', '내용없음')}")
                    st.caption(f"문서 위치: {row.get('reference', '없음')}")
    else:
        # 정상 검색 결과 출력
        for i, row in result_df.iterrows():
            with st.expander(f"[{row.get('category', '분류없음')}] {row.get('title', '제목없음')}"):
                st.info(f"**💡 안전 기준:**\n\n{row.get('answer', '없음')}")
                st.caption(f"문서 위치: {row.get('reference', '없음')}")

# 5. 하단 문의처
st.divider()
col1, col2 = st.columns([1, 2])
with col1:
    st.markdown("**담당자:** 안전팀 백찬주 대리")
    st.markdown("**전화:** 010-2528-5706")
st.caption("📄 시스템 관련 문의사항은 언제든 환영합니다.")
