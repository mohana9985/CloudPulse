from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so "live" imports when run by streamlit

st.set_page_config(page_title="CloudPulse Dashboard", layout="wide")

HERE = Path(__file__).resolve().parent
nav = st.navigation([
    st.Page(HERE / "website_page.py", title="Website workload", icon=":material/shopping_cart:", default=True),
    st.Page(HERE / "cluster_page.py", title="Compute cluster", icon=":material/memory:"),
])
nav.run()
