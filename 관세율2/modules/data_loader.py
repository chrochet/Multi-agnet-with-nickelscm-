import pandas as pd
import streamlit as st
from modules.utils import get_project_root


@st.cache_data
def load_tariff_data():
    """
    금속류 관세율 CSV 로드
    CSV 컬럼: hs_code, desc, mfn_rate, country, source_file, hs2
    """
    csv_path = get_project_root() / "data" / "clean_tariff_metals.csv"

    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception as e:
        raise RuntimeError(f"CSV 로딩 실패: {e}")

    # 결측치 제거
    df = df.fillna("")

    return df
