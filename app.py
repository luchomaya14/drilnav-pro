import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="DrillNav Pro", layout="wide")

st.title("🛢️ DrillNav Pro")
st.write("Build 5 - Lectura robusta + validación + diagnóstico automático")

file = st.file_uploader("Subí tu Excel", type=["xlsx"])

# -------------------------
# FUNCIONES
# -------------------------

def limpiar_surveys(df):
    df = df.copy()

    if df.shape[1] < 11:
        st.error(f"El archivo tiene {df.shape[1]} columnas. Se esperaban al menos 11.")
        return None

    # Nos quedamos con las primeras 11 columnas
    df = df.iloc[:, :11].copy()

    # Asignación manual de nombres según la estructura real observada
    df.columns = [
        "MD",        # col 0
        "INC",       # col 1
        "AZI",       # col 2
        "TVD",       # col 3
        "COL5",      # col 4
        "COL6",      # col 5
        "COL7",      # col 6
        "DLS",       # col 7
        "BUILD",     # col 8
        "Status",    # col 9
        "Tipo"       # col 10
    ]

    # Conversión numérica
    columnas_numericas = ["MD", "INC", "AZI", "TVD", "COL5", "COL6", "COL7", "DLS", "BUILD"]
    for col in columnas_numericas:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Eliminar filas inválidas
    df = df.dropna(subset=["MD", "INC", "AZI"]).copy()

    # Normalizar TVD a positivo si viene con signo negativo
    df["TVD"] = df["TVD"].abs()

    return df


def calcular_dls(df):
    df = df.copy()

    df["Delta_MD"] = df["MD"].diff()
    df["Delta_INC"] = df["INC"].diff()
    df["Delta_AZI"] = df["AZI"].diff()

    # Evitar divisiones raras o pasos cero
    df["Delta_MD"] = df["Delta_MD"].replace(0, np.nan)

    # Aproximación simple de DLS
    df["DLS_calc"] = np.sqrt(
        (df["Delta_INC"].fillna(0))**2 +
        (df["Delta_AZI"].fillna(0))**2
    )

    # Si querés luego lo refinamos a fórmula más petrolera por 30 m o 100 ft
    return df


def calcular_tortuosidad(df):
    df = df.copy()

    if "DLS_calc" not in df.columns:
        df = calcular_dls(df)

    df["Tortuosity"] = df["DLS_calc"].rolling(window=5, min_periods=1).sum()

    return df


def clasificar(df):
    df = df.copy()

    def alerta(row):
        if pd.notna(row["DLS"]) and row["DLS"] > 8:
            return "🔴 Crítico"
        elif pd.notna(row["DLS"]) and row["DLS"] > 5:
            return "🟠 Alto"
        elif pd.notna(row["Tortuosity"]) and row["Tortuosity"] > 100:
            return "🟡 Tortuoso"
        else:
            return "🟢 Normal"

    df["Alerta"] = df.apply(alerta, axis=1)

    return df


def diagnostico(df):
    mensajes = []

    max_dls = df["DLS"].max() if "DLS" in df.columns else np.nan
    max_tort = df["Tortuosity"].max() if "Tortuosity" in df.columns else np.nan

    if pd.notna(max_dls):
        if max_dls > 8:
            mensajes.append("🔴 Trayectoria agresiva: DLS muy alto, riesgo de fatiga, torque y drag.")
        elif max_dls > 5:
            mensajes.append("🟠 DLS elevado: conviene revisar control direccional y suavidad de la trayectoria.")

    if pd.notna(max_tort) and max_tort > 100:
        mensajes.append("🟡 Alta tortuosidad: posible riesgo de key seat, dificultad de casing y aumento de arrastre.")

    if not mensajes:
        mensajes.append("🟢 Trayectoria dentro de parámetros razonables para este análisis preliminar.")

    return mensajes


def validar_columnas(df):
    avisos = []

    if df.empty:
        avisos.append("⚠️ El archivo quedó vacío después de limpiar datos.")
        return avisos

    # MD debería crecer
    if not df["MD"].is_monotonic_increasing:
        avisos.append("⚠️ La columna MD no está en orden ascendente. Revisar el survey.")

    # TVD no debería superar MD en trayectoria realista
    if df["TVD"].max() > df["MD"].max():
        avisos.append("⚠️ La TVD máxima es mayor que la MD máxima. Eso huele raro: revisar mapeo de columnas.")

    # INC razonable
    if df["INC"].max() > 180:
        avisos.append("⚠️ Se detectaron inclinaciones mayores a 180°. Posible columna mal interpretada.")

    # AZI razonable
    if df["AZI"].max() > 360:
        avisos.append("⚠️ Se detectaron azimuts mayores a 360°. Posible columna mal interpretada.")

    # Columnas duplicadas sospechosas
    if "COL5" in df.columns and "COL6" in df.columns:
        if df["COL5"].equals(df["COL6"]):
            avisos.append("ℹ️ COL5 y COL6 son idénticas en todo el archivo. Puede ser correcto, pero merece revisión.")

    return avisos


def comparar_dls(df):
    df = df.copy()

    if "DLS" not in df.columns or "DLS_calc" not in df.columns:
        return df

    df["Dif_DLS"] = (df["DLS"] - df["DLS_calc"]).abs()

    return df


# -------------------------
# APP
# -------------------------

if file:
    try:
        # Leer SIN encabezados
        raw = pd.read_excel(file, engine="openpyxl", header=None)

        df = limpiar_surveys(raw)

        if df is not None and not df.empty:
            df = calcular_dls(df)
            df = calcular_tortuosidad(df)
            df = comparar_dls(df)
            df = clasificar(df)

            st.success("Archivo procesado correctamente")

            # -------------------------
            # VALIDACIONES
            # -------------------------
            st.subheader("🧪 Validación automática del archivo")

            avisos = validar_columnas(df)

            if avisos:
                for aviso in avisos:
                    st.warning(aviso)
            else:
                st.info("No se detectaron inconsistencias estructurales obvias.")

            # -------------------------
            # VISTA PREVIA
            # -------------------------
            st.subheader("🔍 Vista previa del archivo interpretado")
            st.dataframe(df.head(10), use_container_width=True)

            # -------------------------
            # MÉTRICAS
            # -------------------------
            st.subheader("📌 Métricas principales")

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Máx MD", f"{df['MD'].max():.2f}")
            col2.metric("Máx TVD", f"{df['TVD'].max():.2f}")
            col3.metric("Máx DLS", f"{df['DLS'].max():.2f}")
            col4.metric("Máx Tortuosidad", f"{df['Tortuosity'].max():.2f}")

            # -------------------------
            # GRÁFICOS
            # -------------------------
            st.subheader("📈 Gráficos")

            st.write("**TVD vs MD**")
            st.line_chart(df.set_index("MD")[["TVD"]])

            st.write("**DLS reportado vs DLS calculado**")
            st.line_chart(df.set_index("MD")[["DLS", "DLS_calc"]])

            st.write("**Tortuosidad vs MD**")
            st.line_chart(df.set_index("MD")[["Tortuosity"]])

            # -------------------------
            # DIAGNÓSTICO
            # -------------------------
            st.subheader("🧠 Diagnóstico automático")

            for msg in diagnostico(df):
                st.write(msg)

            # -------------------------
            # DIFERENCIAS DLS
            # -------------------------
            st.subheader("⚖️ Comparación entre DLS reportado y DLS calculado")

            if "Dif_DLS" in df.columns:
                max_dif = df["Dif_DLS"].max()
                st.write(f"Diferencia máxima detectada: **{max_dif:.2f}**")

                diferencias_altas = df[df["Dif_DLS"] > 2].copy()

                if diferencias_altas.empty:
                    st.info("No se detectaron diferencias grandes entre DLS reportado y DLS calculado.")
                else:
                    st.warning("Se detectaron diferencias relevantes entre DLS reportado y calculado.")
                    st.dataframe(
                        diferencias_altas[["MD", "INC", "AZI", "DLS", "DLS_calc", "Dif_DLS"]],
                        use_container_width=True
                    )

            # -------------------------
            # PUNTOS CRÍTICOS
            # -------------------------
            st.subheader("🚨 Puntos críticos")

            criticos = df[df["Alerta"] != "🟢 Normal"].copy()

            if criticos.empty:
                st.info("No se detectaron puntos críticos.")
            else:
                st.dataframe(
                    criticos[["MD", "INC", "AZI", "TVD", "DLS", "DLS_calc", "Tortuosity", "Alerta"]],
                    use_container_width=True
                )

            # -------------------------
            # TABLA COMPLETA
            # -------------------------
            st.subheader("📊 Tabla completa")
            st.dataframe(df, use_container_width=True)

        else:
            st.error("No se pudieron procesar los datos.")

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

else:
    st.write("Esperando archivo...")
