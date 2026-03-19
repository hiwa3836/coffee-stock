import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0f172a !important; color: #f1f5f9 !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 5px; background-color: #1e293b !important; padding: 5px; border-radius: 10px; }
        .stTabs [data-baseweb="tab"] { height: 40px; background-color: #334155 !important; color: #94a3b8 !important; font-size: 0.85rem; padding: 0 12px !important; border-radius: 6px !important; font-weight: bold; }
        .stTabs [aria-selected="true"] { background-color: #2563eb !important; color: white !important; }
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"]:has(.item-name) { flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; }
            div[data-testid="stHorizontalBlock"]:has(.item-name) > div:nth-child(1) { width: 55% !important; flex: 1 1 55% !important; min-width: 0 !important; }
            div[data-testid="stHorizontalBlock"]:has(.item-name) > div:nth-child(2) { width: 45% !important; flex: 1 1 45% !important; min-width: 120px !important; }
        }
        div[data-baseweb="input"] > div { background-color: #0f172a !important; }
        [data-testid="stExpander"] { background-color: #1e293b !important; border-radius: 10px !important; border: 1px solid #334155 !important; margin-bottom: 8px !important; }
        [data-testid="stExpander"] summary p { font-weight: bold !important; color: #60a5fa !important; font-size: 0.95rem !important; }
        .item-name { font-size: 0.95rem; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .item-cap { font-size: 0.75rem; color: #94a3b8; }
        hr { border-top: 1px solid #334155 !important; margin: 8px 0 !important; opacity: 0.5; }
        .block-container { padding: 1.5rem 0.6rem !important; }
        #MainMenu, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
