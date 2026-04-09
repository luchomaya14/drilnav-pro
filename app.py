import streamlit as st
import pandas as pd

st.title("🛢️ DrillNav Pro")

file = st.file_uploader("Subí tu Excel", type=["xlsx"])

if file:
    df = pd.read_excel(file)
    st.write(df.head())
else:
    st.write("Esperando archivo...")
