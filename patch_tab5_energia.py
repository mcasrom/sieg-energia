#!/usr/bin/env python3
"""
patch_tab5_energia.py
Añade Tab 5 Mix Energético + Predicción al dashboard de energía.
"""
import os, shutil
from datetime import datetime

path = os.path.expanduser("~/sieg-energia/dashboard/app.py")
shutil.copy2(path, path + f".bak_{datetime.now().strftime('%Y%m%d_%H%M')}")

with open(path, "r") as f:
    content = f.read()

# 1. Actualizar carga de datos para incluir generación
OLD_CACHE = """@st.cache_data(ttl=300)
def cargar_datos():
    try:
        if os.path.exists(DB_PATH):
            conn = duckdb.connect(DB_PATH, read_only=True)
            df_hoy   = conn.execute("SELECT * FROM pvpc WHERE fecha = CURRENT_DATE ORDER BY hora").df()
            df_stats = conn.execute("SELECT * FROM pvpc_stats ORDER BY fecha DESC LIMIT 30").df()
            df_hist  = conn.execute("SELECT * FROM pvpc WHERE fecha >= CURRENT_DATE - INTERVAL 30 DAY ORDER BY datetime").df()
            conn.close()
        else:
            df_hoy   = pd.read_parquet(os.path.join(EXP_DIR, "pvpc_hoy.parquet")) if os.path.exists(os.path.join(EXP_DIR, "pvpc_hoy.parquet")) else pd.DataFrame()
            df_stats = pd.read_parquet(os.path.join(EXP_DIR, "pvpc_stats.parquet")) if os.path.exists(os.path.join(EXP_DIR, "pvpc_stats.parquet")) else pd.DataFrame()
            df_hist  = pd.read_parquet(os.path.join(EXP_DIR, "pvpc.parquet")) if os.path.exists(os.path.join(EXP_DIR, "pvpc.parquet")) else pd.DataFrame()
        return df_hoy, df_stats, df_hist
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_hoy, df_stats, df_hist = cargar_datos()"""

NEW_CACHE = """@st.cache_data(ttl=300)
def cargar_datos():
    try:
        if os.path.exists(DB_PATH):
            conn = duckdb.connect(DB_PATH, read_only=True)
            df_hoy   = conn.execute("SELECT * FROM pvpc WHERE fecha = CURRENT_DATE ORDER BY hora").df()
            df_stats = conn.execute("SELECT * FROM pvpc_stats ORDER BY fecha DESC LIMIT 30").df()
            df_hist  = conn.execute("SELECT * FROM pvpc WHERE fecha >= CURRENT_DATE - INTERVAL 30 DAY ORDER BY datetime").df()
            try:
                df_gen   = conn.execute("SELECT * FROM generacion WHERE fecha = CURRENT_DATE ORDER BY valor_mwh DESC").df()
                df_gen_h = conn.execute("SELECT * FROM generacion WHERE fecha >= CURRENT_DATE - INTERVAL 30 DAY ORDER BY fecha DESC").df()
            except:
                df_gen = pd.DataFrame()
                df_gen_h = pd.DataFrame()
            conn.close()
        else:
            df_hoy   = pd.read_parquet(os.path.join(EXP_DIR, "pvpc_hoy.parquet")) if os.path.exists(os.path.join(EXP_DIR, "pvpc_hoy.parquet")) else pd.DataFrame()
            df_stats = pd.read_parquet(os.path.join(EXP_DIR, "pvpc_stats.parquet")) if os.path.exists(os.path.join(EXP_DIR, "pvpc_stats.parquet")) else pd.DataFrame()
            df_hist  = pd.read_parquet(os.path.join(EXP_DIR, "pvpc.parquet")) if os.path.exists(os.path.join(EXP_DIR, "pvpc.parquet")) else pd.DataFrame()
            df_gen   = pd.read_parquet(os.path.join(EXP_DIR, "gen_hoy.parquet")) if os.path.exists(os.path.join(EXP_DIR, "gen_hoy.parquet")) else pd.DataFrame()
            df_gen_h = pd.read_parquet(os.path.join(EXP_DIR, "generacion.parquet")) if os.path.exists(os.path.join(EXP_DIR, "generacion.parquet")) else pd.DataFrame()
        return df_hoy, df_stats, df_hist, df_gen, df_gen_h
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_hoy, df_stats, df_hist, df_gen, df_gen_h = cargar_datos()"""

if OLD_CACHE in content:
    content = content.replace(OLD_CACHE, NEW_CACHE)
    print("Cache OK")
else:
    print("Cache NOT FOUND")

# 2. Actualizar tabs para añadir Tab 5
OLD_TABS = 'tab1, tab2, tab3, tab4 = st.tabs(['
NEW_TABS = 'tab1, tab2, tab3, tab4, tab5 = st.tabs(['

OLD_TABS_LIST = '"⚡ Precio hoy",\n    "📈 Histórico",\n    "💡 Consejos ahorro",\n    "📖 Guía"'
NEW_TABS_LIST = '"⚡ Precio hoy",\n    "📈 Histórico",\n    "💡 Consejos ahorro",\n    "🔋 Mix Energético",\n    "📖 Guía"'

content = content.replace(OLD_TABS, NEW_TABS, 1)
content = content.replace(OLD_TABS_LIST, NEW_TABS_LIST, 1)

# 3. Renombrar tab4 guía a tab5
content = content.replace('with tab4:\n    st.header("📖 Guía de uso")', 'with tab5:\n    st.header("📖 Guía de uso")')

# 4. Añadir Tab 4 Mix Energético antes del footer
OLD_FOOTER = 'st.markdown("---")\nst.markdown("""\n<div style=\'text-align:center; font-size:0.72rem; opacity:0.35; font-family:monospace\'>'

NEW_TAB4 = '''# ── Tab 4: Mix Energético + Predicción ──────────────────
with tab4:
    st.header("🔋 Mix de Generación Eléctrica")

    if df_gen.empty:
        st.info("Sin datos de generación. Ejecuta el pipeline primero.")
    else:
        # KPIs renovable vs no renovable
        total     = df_gen["valor_mwh"].sum()
        renovable = df_gen[df_gen["es_renovable"] == True]["valor_mwh"].sum()
        no_ren    = total - renovable
        pct_ren   = renovable / total * 100 if total > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("⚡ Generación total", f"{total/1000:.1f} GWh")
        c2.metric("🌱 Renovable", f"{pct_ren:.1f}%", f"{renovable/1000:.1f} GWh")
        c3.metric("🏭 No renovable", f"{100-pct_ren:.1f}%", f"{no_ren/1000:.1f} GWh")
        c4.metric("☀️ Solar", f"{df_gen[df_gen['fuente'].str.contains('Solar', na=False)]['valor_mwh'].sum()/1000:.1f} GWh")

        st.markdown("---")

        # Gráfico barras por fuente
        df_gen_chart = df_gen[df_gen["valor_mwh"] > 0].copy()
        df_gen_chart["GWh"] = (df_gen_chart["valor_mwh"] / 1000).round(2)
        df_gen_chart["tipo"] = df_gen_chart["es_renovable"].map({True: "Renovable", False: "No renovable"})

        color_scale = alt.Scale(
            domain=["Renovable", "No renovable"],
            range=["#00cc33", "#ef4444"]
        )

        chart_gen = alt.Chart(df_gen_chart).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("GWh:Q", title="GWh"),
            y=alt.Y("fuente:N", sort="-x", title="Fuente"),
            color=alt.Color("tipo:N", scale=color_scale, title="Tipo"),
            tooltip=["fuente:N", "GWh:Q", "tipo:N"]
        ).properties(height=350, title="Mix de generación eléctrica hoy")
        st.altair_chart(chart_gen, use_container_width=True)

        st.markdown("---")

        # Predicción precio próximas horas
        st.subheader("🔮 Predicción precio próximas horas")
        st.caption("Modelo de regresión lineal entrenado con datos históricos PVPC")

        if not df_hist.empty and len(df_hist) >= 48:
            try:
                from sklearn.linear_model import LinearRegression
                import numpy as np

                df_model = df_hist.copy()
                df_model["datetime"] = pd.to_datetime(df_model["datetime"], errors="coerce")
                df_model["hora"]     = df_model["datetime"].dt.hour
                df_model["dia_sem"]  = df_model["datetime"].dt.dayofweek
                df_model["hora_sin"] = np.sin(2 * np.pi * df_model["hora"] / 24)
                df_model["hora_cos"] = np.cos(2 * np.pi * df_model["hora"] / 24)

                features = ["hora", "dia_sem", "hora_sin", "hora_cos"]
                X = df_model[features].values
                y = df_model["precio"].values

                model = LinearRegression()
                model.fit(X, y)

                from datetime import datetime as dt
                hora_actual = dt.now().hour
                predicciones = []
                for h in range(hora_actual + 1, min(hora_actual + 7, 24)):
                    dia_sem  = dt.now().weekday()
                    h_sin    = np.sin(2 * np.pi * h / 24)
                    h_cos    = np.cos(2 * np.pi * h / 24)
                    pred     = model.predict([[h, dia_sem, h_sin, h_cos]])[0]
                    predicciones.append({"Hora": f"{h:02d}:00", "Precio predicho €/MWh": round(pred, 2)})

                if predicciones:
                    df_pred = pd.DataFrame(predicciones)

                    chart_pred = alt.Chart(df_pred).mark_line(
                        point=True, color="#facc15", strokeDash=[4, 2]
                    ).encode(
                        x=alt.X("Hora:N", title="Hora"),
                        y=alt.Y("Precio predicho €/MWh:Q", title="€/MWh"),
                        tooltip=["Hora:N", "Precio predicho €/MWh:Q"]
                    ).properties(height=250, title="Predicción precio próximas horas (regresión lineal)")
                    st.altair_chart(chart_pred, use_container_width=True)

                    st.dataframe(df_pred, use_container_width=True, hide_index=True)

                    st.info(
                        "⚠️ Predicción orientativa basada en patrones históricos. "
                        "El precio real depende del mercado mayorista en tiempo real. "
                        f"R² del modelo: {model.score(X, y):.3f}"
                    )
            except Exception as e:
                st.warning(f"Error en predicción: {e}")
        else:
            st.info("Se necesitan al menos 48 horas de datos históricos para la predicción.")

        st.markdown("---")

        # Histórico renovable %
        if not df_gen_h.empty:
            st.subheader("📈 Evolución % renovable (últimos 30 días)")
            df_gen_h["fecha"] = pd.to_datetime(df_gen_h["fecha"], errors="coerce")
            df_ren_hist = df_gen_h.groupby("fecha").apply(
                lambda x: pd.Series({
                    "pct_renovable": x[x["es_renovable"] == True]["valor_mwh"].sum() / x["valor_mwh"].sum() * 100
                    if x["valor_mwh"].sum() > 0 else 0
                })
            ).reset_index()

            chart_ren = alt.Chart(df_ren_hist).mark_area(
                color="#00cc33", opacity=0.3, line={"color": "#00cc33"}
            ).encode(
                x=alt.X("fecha:T", title="Fecha"),
                y=alt.Y("pct_renovable:Q", title="% Renovable", scale=alt.Scale(domain=[0, 100])),
                tooltip=["fecha:T", alt.Tooltip("pct_renovable:Q", format=".1f", title="% Renovable")]
            ).properties(height=200)
            st.altair_chart(chart_ren, use_container_width=True)

''' + OLD_FOOTER

if OLD_FOOTER in content:
    content = content.replace(OLD_FOOTER, NEW_TAB4)
    print("Tab 4 Mix OK")
else:
    print("Footer NOT FOUND")

with open(path, "w") as f:
    f.write(content)

import ast
ast.parse(open(path).read())
print("Sintaxis OK")
