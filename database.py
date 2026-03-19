import streamlit as st
from supabase import create_client, Client

# Streamlit의 캐싱을 활용하여 DB 연결 속도 최적화
@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# 이 supabase 객체를 다른 파일에서 불러다 씁니다.
supabase = get_supabase_client()
