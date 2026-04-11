import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="DrillNav Pro", layout="wide")

st.title("🛢️ DrillNav Pro")
st.write("Build 6 Galáctico - 3D + KOP automático + markers operacionales")

file = st.file_uploader("Subí tu Excel", type=["xlsx"])

# -------------------------
# FUNCIONES
# -------------------------

def limpiar_surveys(df):
    df = df.copy()

    if df.shape[1] < 11:
        st.error(f"El archivo tiene {df.shape[1]} columnas. Se esperaban al menos 11.")
        return None

    df = df.iloc[:, :11].copy()

    # Estructura observada en tu archivo
    df.columns = [
        "MD",        # 0
        "INC",       # 1
        "AZI",       # 2
        "TVD",       # 3
        "X",         # 4
        "Y",         # 5
        "COL7",      # 6
        "DLS",       # 7
        "BUILD",     # 8
        "Status",    # 9
        "Tipo"       # 10
    ]

    columnas_numericas = ["MD", "INC", "AZI", "TVD", "X", "Y", "COL7", "DLS", "BUILD"]
    for col in columnas_numericas:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["MD", "INC", "AZI"]).copy()

    # Normalización básica
    df["TVD"] = df["TVD"].abs()

    # Orden por MD por si el archivo viene desordenado
    df = df.sort_values("MD").reset_index(drop=True)

    return df


def calcular_dls_aprox(df):
    df = df.copy()

    df["Delta_MD"] = df["MD"].diff()
    df["Delta_INC"] = df["INC"].diff()
    df["Delta_AZI"] = df["AZI"].diff()

    # Evitar valores raros por paso cero
    df["Delta_MD"] = df["Delta_MD"].replace(0, np.nan)

    # Aproximación simple para chequeo rápido
    df["DLS_calc"] = np.sqrt(
        (df["Delta_INC"].fillna(0))**2 +
        (df["Delta_AZI"].fillna(0))**2
    )

    return df


def calcular_microtortuosidad(df, ventana=5):
    df = df.copy()

    if "DLS_calc" not in df.columns:
        df = calcular_dls_aprox(df)

    # Índice simple de variación local
    df["MicroVar"] = (
        df["INC"].diff().abs().fillna(0) +
        df["AZI"].diff().abs().fillna(0)
    )

    df["Tortuosity"] = df["MicroVar"].rolling(window=ventana, min_periods=1).sum()

    return df


def clasificar(df):
    df = df.copy()

    def alerta(row):
        if pd.notna(row["DLS"]) and row["DLS"] > 8:
            return "🔴 Crítico"
        elif pd.notna(row["DLS"]) and row["DLS"] > 5:
            return "🟠 Alto"
        elif pd.notna(row["Tortuosity"]) and row["Tortuosity"] > 25:
            return "🟡 Tortuoso"
        else:
            return "🟢 Normal"

    df["Alerta"] = df.apply(alerta, axis=1)
    return df


def validar_columnas(df):
    avisos = []

    if df.empty:
        avisos.append("⚠️ El archivo quedó vacío después de la limpieza.")
        return avisos

    if not df["MD"].is_monotonic_increasing:
        avisos.append("⚠️ La MD no está en orden ascendente.")

    if df["TVD"].max() > df["MD"].max():
        avisos.append("⚠️ La TVD máxima es mayor que la MD máxima. Revisar mapeo de columnas.")

    if df["INC"].max() > 180:
        avisos.append("⚠️ Se detectaron INC mayores a 180°. Eso no huele bien.")

    if df["AZI"].max() > 360:
        avisos.append("⚠️ Se detectaron AZI mayores a 360°. Revisar columnas.")

    if df["X"].equals(df["Y"]):
        avisos.append("ℹ️ X e Y son idénticas en todo el archivo. Puede ser correcto, pero merece revisión.")

    return avisos


def comparar_dls(df):
    df = df.copy()

    if "DLS" in df.columns and "DLS_calc" in df.columns:
        df["Dif_DLS"] = (df["DLS"] - df["DLS_calc"]).abs()

    return df





def obtener_puntos_clave(df):
    puntos = {}

    # TD
    idx_td = df["MD"].idxmax()
    puntos["TD"] = df.loc[idx_td]

    # Máx DLS
    if df["DLS"].notna().any():
        idx_max_dls = df["DLS"].idxmax()
        puntos["Max DLS"] = df.loc[idx_max_dls]

    # Máx Tortuosidad
    if df["Tortuosity"].notna().any():
        idx_max_tort = df["Tortuosity"].idxmax()
        puntos["Max Tortuosidad"] = df.loc[idx_max_tort]

    return puntos


def diagnostico(df, event_depth=None):
    mensajes = []

    max_dls = df["DLS"].max() if "DLS" in df.columns else np.nan
    max_tort = df["Tortuosity"].max() if "Tortuosity" in df.columns else np.nan

    if pd.notna(max_dls):
        if max_dls > 8:
            mensajes.append("🔴 Trayectoria agresiva: DLS muy alto, riesgo de torque, drag y fatiga.")
        elif max_dls > 5:
            mensajes.append("🟠 DLS elevado: revisar control direccional y suavidad de la trayectoria.")

    if pd.notna(max_tort):
        if max_tort > 35:
            mensajes.append("🔴 Microtortuosidad muy alta: zona candidata a problemas mecánicos reales.")
        elif max_tort > 25:
            mensajes.append("🟡 Tortuosidad elevada: revisar comportamiento de casing, drag y restricciones locales.")

    if event_depth is not None:
        cercano = df.iloc[(df["MD"] - event_depth).abs().argsort()[:1]]
        if not cercano.empty:
            md_ev = cercano["MD"].values[0]
            tort_ev = cercano["Tortuosity"].values[0]
            dls_ev = cercano["DLS"].values[0] if pd.notna(cercano["DLS"].values[0]) else np.nan

            if pd.notna(tort_ev) and tort_ev > 25:
                mensajes.append(
                    f"🎯 El evento operacional cargado cerca de MD {md_ev:.2f} coincide con una zona de tortuosidad elevada."
                )

            if pd.notna(dls_ev) and dls_ev > 5:
                mensajes.append(
                    f"🎯 El evento operacional cargado cerca de MD {md_ev:.2f} también coincide con DLS elevado."
                )

    if not mensajes:
        mensajes.append("🟢 No se detectaron alertas relevantes en este análisis preliminar.")

    return mensajes


def buscar_evento_cercano(df, event_depth):
    if event_depth is None:
        return None

    idx = (df["MD"] - event_depth).abs().idxmin()
    return df.loc[idx]


def crear_grafico_3d(df, kop_row=None, puntos_clave=None, evento_row=None, evento_nombre="Evento"):
    fig = go.Figure()

    # Trayectoria principal
    fig.add_trace(go.Scatter3d(
        x=df["X"],
        y=df["Y"],
        z=-df["TVD"],
        mode="lines",
        name="Trayectoria",
        line=dict(width=6, color="deepskyblue"),
        hovertemplate=(
            "MD: %{customdata[0]:.2f}<br>"
            "INC: %{customdata[1]:.2f}<br>"
            "AZI: %{customdata[2]:.2f}<br>"
            "TVD: %{customdata[3]:.2f}<extra></extra>"
        ),
        customdata=np.stack([df["MD"], df["INC"], df["AZI"], df["TVD"]], axis=-1)
    ))

    

    # Puntos clave
    if puntos_clave:
        for nombre, row in puntos_clave.items():
            fig.add_trace(go.Scatter3d(
                x=[row["X"]],
                y=[row["Y"]],
                z=[-row["TVD"]],
                mode="markers+text",
                name=nombre,
                text=[nombre],
                textposition="top center",
                marker=dict(size=6),
                hovertemplate=(
                    f"{nombre}<br>"
                    f"MD: {row['MD']:.2f}<br>"
                    f"TVD: {row['TVD']:.2f}<extra></extra>"
                )
            ))

    # Evento manual
    if evento_row is not None:
        fig.add_trace(go.Scatter3d(
            x=[evento_row["X"]],
            y=[evento_row["Y"]],
            z=[-evento_row["TVD"]],
            mode="markers+text",
            name=evento_nombre,
            text=[evento_nombre],
            textposition="top center",
            marker=dict(size=8, color="red", symbol="x"),
            hovertemplate=(
                f"{evento_nombre}<br>"
                f"MD: {evento_row['MD']:.2f}<br>"
                f"TVD: {evento_row['TVD']:.2f}<br>"
                f"DLS: {evento_row['DLS']:.2f}<br>"
                f"Tortuosidad: {evento_row['Tortuosity']:.2f}<extra></extra>"
            )
        ))

    fig.update_layout(
        title="Trayectoria 3D del pozo",
        scene=dict(
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="TVD",
            bgcolor="rgba(0,0,0,0)"
        ),
        height=750,
        margin=dict(l=0, r=0, b=0, t=50)
    )

    return fig


def crear_grafico_planta(df, kop_row=None, puntos_clave=None, evento_row=None, evento_nombre="Evento"):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["X"],
        y=df["Y"],
        mode="lines+markers",
        name="Planta",
        hovertemplate=(
            "MD: %{customdata[0]:.2f}<br>"
            "INC: %{customdata[1]:.2f}<br>"
            "AZI: %{customdata[2]:.2f}<extra></extra>"
        ),
        customdata=np.stack([df["MD"], df["INC"], df["AZI"]], axis=-1)
    ))


    if puntos_clave:
        for nombre, row in puntos_clave.items():
            fig.add_trace(go.Scatter(
                x=[row["X"]],
                y=[row["Y"]],
                mode="markers+text",
                name=nombre,
                text=[nombre],
                textposition="top center"
            ))

    if evento_row is not None:
        fig.add_trace(go.Scatter(
            x=[evento_row["X"]],
            y=[evento_row["Y"]],
            mode="markers+text",
            name=evento_nombre,
            text=[evento_nombre],
            textposition="top center"
        ))

    fig.update_layout(
        title="Vista en planta (X vs Y)",
        xaxis_title="X",
        yaxis_title="Y",
        height=600
    )

    return fig


# -------------------------
# APP
# -------------------------

if file:
    try:
        raw = pd.read_excel(file, engine="openpyxl", header=None)
        df = limpiar_surveys(raw)

        if df is not None and not df.empty:
            df = calcular_dls_aprox(df)
            df = calcular_microtortuosidad(df, ventana=5)
            df = comparar_dls(df)
            df = clasificar(df)

            puntos_clave = obtener_puntos_clave(df)

            st.success("Archivo procesado correctamente")

            # -------------------------
            # PANEL DE EVENTO MANUAL
            # -------------------------
            st.subheader("🎯 Evento operacional manual")

            col_ev1, col_ev2 = st.columns(2)

            with col_ev1:
                evento_nombre = st.text_input(
                    "Nombre del evento",
                    value="Asentamiento casing"
                )

            with col_ev2:
                evento_md = st.number_input(
                    "MD del evento",
                    min_value=0.0,
                    value=3116.87,
                    step=0.01
                )

            evento_row = buscar_evento_cercano(df, evento_md)

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
            # RESUMEN DE PUNTOS CLAVE
            # -------------------------
            st.subheader("📍 Puntos automáticos detectados")

            resumen = []

            if kop_row is not None:
                resumen.append({
                    "Punto": "KOP",
                    "MD": round(kop_row["MD"], 2),
                    "INC": round(kop_row["INC"], 2),
                    "AZI": round(kop_row["AZI"], 2),
                    "TVD": round(kop_row["TVD"], 2)
                })

            for nombre, row in puntos_clave.items():
                resumen.append({
                    "Punto": nombre,
                    "MD": round(row["MD"], 2),
                    "INC": round(row["INC"], 2),
                    "AZI": round(row["AZI"], 2),
                    "TVD": round(row["TVD"], 2)
                })

            if evento_row is not None:
                resumen.append({
                    "Punto": evento_nombre,
                    "MD": round(evento_row["MD"], 2),
                    "INC": round(evento_row["INC"], 2),
                    "AZI": round(evento_row["AZI"], 2),
                    "TVD": round(evento_row["TVD"], 2)
                })

            if resumen:
                st.dataframe(pd.DataFrame(resumen), use_container_width=True)

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
            # GRÁFICOS 2D
            # -------------------------
            st.subheader("📈 Gráficos")

            st.write("**TVD vs MD**")
            st.line_chart(df.set_index("MD")[["TVD"]])

            st.write("**DLS reportado vs DLS calculado**")
            st.line_chart(df.set_index("MD")[["DLS", "DLS_calc"]])

            st.write("**Tortuosidad vs MD**")
            st.line_chart(df.set_index("MD")[["Tortuosity"]])

            # -------------------------
            # VISTA EN PLANTA
            # -------------------------
            st.subheader("🧭 Vista en planta")
            fig_planta = crear_grafico_planta(
                df,
                kop_row=kop_row,
                puntos_clave=puntos_clave,
                evento_row=evento_row,
                evento_nombre=evento_nombre
            )
            st.plotly_chart(fig_planta, use_container_width=True)

            # -------------------------
            # VISTA 3D
            # -------------------------
            st.subheader("🌌 Trayectoria 3D")
            fig_3d = crear_grafico_3d(
                df,
                kop_row=kop_row,
                puntos_clave=puntos_clave,
                evento_row=evento_row,
                evento_nombre=evento_nombre
            )
            st.plotly_chart(fig_3d, use_container_width=True)

            # -------------------------
            # DIAGNÓSTICO
            # -------------------------
            st.subheader("🧠 Diagnóstico automático")
            for msg in diagnostico(df, event_depth=evento_md):
                st.write(msg)

            # -------------------------
            # COMPARACIÓN DLS
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
