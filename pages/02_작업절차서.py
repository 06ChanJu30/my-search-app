import streamlit as st
import os

# --- 상단 홈 버튼 ---
st.page_link("app.py", label="메인으로 돌아가기", icon="🏠")
st.markdown("---")

# 1. 경로 설정
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base_folder_path = os.path.join(current_dir, "manual_data")

# --- 🚨 [관리자용 디버깅 투시경] 🚨 ---
# (서버가 실제로 어떤 폴더들을 인식하고 있는지 화면에 보여줍니다)
with st.expander("🛠️ (관리자용) 현재 서버가 인식 중인 폴더 확인", expanded=False):
    if os.path.exists(base_folder_path):
        all_items = os.listdir(base_folder_path)
        st.write(f"📂 **`manual_data` 폴더 안의 모든 항목:** {all_items}")
        st.info("💡 만약 여기에 올리신 폴더 이름이 안 보인다면, 깃허브에 제대로 안 올라간 것입니다!")
    else:
        st.error("❌ `manual_data` 폴더 자체를 찾을 수 없습니다.")
# ------------------------------------

# 2. 스타일 설정
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.1rem; font-weight: bold;
    }
    .img-caption {
        font-size: 0.9rem; color: #555; margin-bottom: 20px; text-align: center; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# 3. 폴더 존재 여부 확인
if not os.path.exists(base_folder_path):
    st.stop()

# 4. 1단계: 대분류 선택 (화면 중앙 드롭다운)
categories = sorted([d for d in os.listdir(base_folder_path) if os.path.isdir(os.path.join(base_folder_path, d))])

if not categories:
    st.warning("📂 'manual_data' 폴더 안에 대분류 폴더가 없습니다.")
    st.stop()

st.title("📖 작업 절차서 열람")
selected_category = st.selectbox("📂 확인할 작업 그룹(대분류)을 선택하세요:", categories)
st.markdown("---")

# 5. 메인 화면 구성 (중분류/소분류)
category_path = os.path.join(base_folder_path, selected_category)
topics = sorted([d for d in os.listdir(category_path) if os.path.isdir(os.path.join(category_path, d))])

if topics:
    # 2단계: 상단 탭 (중분류)
    tabs = st.tabs(topics)
    
    for i, topic in enumerate(topics):
        with tabs[i]:
            topic_path = os.path.join(category_path, topic)
            sub_folders = sorted([d for d in os.listdir(topic_path) if os.path.isdir(os.path.join(topic_path, d))])
            
            # 3단계: 확장형 박스 (소분류)
            if sub_folders:
                for sub in sub_folders:
                    sub_path = os.path.join(topic_path, sub)
                    images = sorted([f for f in os.listdir(sub_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
                    
                    with st.expander(f"📌 {sub} (눌러서 내용 보기)", expanded=False):
                        if images:
                            for img_file in images:
                                caption = os.path.splitext(img_file)[0]
                                display_caption = caption.split("_", 1)[1] if "_" in caption else caption
                                st.image(os.path.join(sub_path, img_file), use_container_width=True)
                                st.markdown(f"<div class='img-caption'>{display_caption}</div>", unsafe_allow_html=True)
                        else:
                            st.info("이미지가 없습니다.")
            else:
                images_in_root = sorted([f for f in os.listdir(topic_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
                if images_in_root:
                     for img_file in images_in_root:
                        st.image(os.path.join(topic_path, img_file), use_container_width=True)
                else:
                    st.warning("하위 폴더나 이미지가 없습니다.")
else:
    st.info("해당 작업 그룹에 등록된 내용이 없습니다.")

# --- 하단 문의처 (사이드바 공통) ---
with st.sidebar:
    st.markdown("---")
    st.caption("** 안전팀 (백찬주 대리)**")
    st.code("010-2528-5706", language="python")
    st.markdown("📧 [이메일 보내기](mailto:king990630@gmail.com)")
