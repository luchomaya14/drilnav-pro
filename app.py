import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="DrillNav Pro", layout="wide")

st.title("🛢️ DrillNav Pro")
st.write("Build 4 - Gráficos + diagnóstico automático")

file = st.file_uploader("Subí tu Excel", type=["xlsx"])

# -------------------------
# FUNCIONES
# -------------------------

def limpiar_surveys(df):
    df = df.copy()

    if df.shape[1] < 11:
        st.error(f"El archivo tiene {df.shape[1]} columnas. Se esperaban al menos 11.")
        return None

    df = df.iloc[:, :11]
    df.columns = [
        "MD", "INC", "AZI", "MD_dup",
        "X", "Y", "Z_TVD",
        "DLS", "Build",
        "Status", "Tipo"
    ]

    for col in ["MD", "INC", "AZI", "X", "Y", "Z_TVD", "DLS"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["MD", "INC", "AZI"]).copy()
    df["TVD"] = df["Z_TVD"].abs()

    return df


def calcular_tortuosidad(df):
    df = df.copy()

    df["DLS_calc"] = np.sqrt(
        (df["INC"].diff().fillna(0))**2 +
        (df["AZI"].diff().fillna(0))**2
    )

    df["Tortuosity"] = df["DLS_calc"].rolling(window=5, min_periods=1).sum()

    return df


def clasificar(df):
    df = df.copy()

    def alerta(row):
        if row["DLS"] > 8:
            return "🔴 Crítico"
        elif row["DLS"] > 5:
            return "🟠 Alto"
        elif row["Tortuosity"] > 100:
            return "🟡 Tortuoso"
        else:
            return "🟢 Normal"

    df["Alerta"] = df.apply(alerta, axis=1)

    return df


def diagnostico(df):
    mensajes = []

    max_dls = df["DLS"].max()
    max_tort = df["Tortuosity"].max()

    if max_dls > 8:
        mensajes.append("🔴 Trayectoria agresiva: DLS muy alto, riesgo de fatiga y torque")
    elif max_dls > 5:
        mensajes.append("🟠 DLS elevado: revisar control direccional")

    if max_tort > 100:
        mensajes.append("🟡 Alta tortuosidad: posible key seat y problemas de casing")

    if not mensajes:
        mensajes.append("🟢 Trayectoria dentro de parámetros normales")

    return mensajes


# -------------------------
# APP
# -------------------------

if file:
    try:
        raw = pd.read_excel(file, engine="openpyxl")

        df = limpiar_surveys(raw)

        if df is not None and not df.empty:

            df = calcular_tortuosidad(df)
            df = clasificar(df)

            st.success("Archivo procesado correctamente")

            # MÉTRICAS
            col1, col2, col3 = st.columns(3)

            col1.metric("Máx MD", f"{df['MD'].max():.2f}")
            col2.metric("Máx TVD", f"{df['TVD'].max():.2f}")
            col3.metric("Máx DLS", f"{df['DLS'].max():.2f}")

            # GRÁFICOS
            st.subheader("📈 Gráficos")

            st.line_chart(df.set_index("MD")["TVD"])
            st.line_chart(df.set_index("MD")["DLS"])
            st.line_chart(df.set_index("MD")["Tortuosity"])

            # DIAGNÓSTICO
            st.subheader("🧠 Diagnóstico automático")

            for msg in diagnostico(df):
                st.write(msg)

            # PUNTOS CRÍTICOS
            st.subheader("🚨 Puntos críticos")

            criticos = df[df["Alerta"] != "🟢 Normal"]

            if criticos.empty:
                st.info("No se detectaron puntos críticos")
            else:
                st.dataframe(
                    criticos[["MD", "INC", "AZI", "TVD", "DLS", "Tortuosity", "Alerta"]],
                    use_container_width=True
                )

            # TABLA COMPLETA
            st.subheader("📊 Tabla completa")
            st.dataframe(df, use_container_width=True)

        else:
            st.error("No se pudieron procesar los datos")

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

else:
    st.write("Esperando archivo...")
