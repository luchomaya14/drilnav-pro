import streamlit as st
import pandas as pd

st.title("🛢️ DrillNav Pro")
st.write("Build 2")

file = st.file_uploader("Subí tu Excel", type=["xlsx"])

if file:
    try:
        df = pd.read_excel(file, engine="openpyxl")
        st.success("Archivo cargado correctamente")
        st.write(df.head())
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
else:
    st.write("Esperando archivo...")
