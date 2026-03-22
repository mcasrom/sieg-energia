#!/usr/bin/env python3
"""
app.py
SIEG Monitor Energético España

Dashboard precio luz PVPC en tiempo real.

Autor : M. Castillo · mybloggingnotes@gmail.com
© 2026 M. Castillo
"""

import os
import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import duckdb
import altair as alt
from datetime import datetime, date, timedelta

st.set_page_config(
    page_title="SIEG Monitor Energético · Precio Luz España",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Detección entorno ─────────────────────────────────────
_local  = os.path.expanduser("~/sieg-energia")
_cloud  = "/mount/src/sieg-energia"
_script = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_script)
BASE_DIR = next(
    (p for p in [_local, _cloud, _parent]
     if os.path.exists(os.path.join(p, "data", "exports"))),
    _parent
)
DB_PATH  = os.path.join(BASE_DIR, "data", "processed", "energia.duckdb")
EXP_DIR  = os.path.join(BASE_DIR, "data", "exports")

# ── Logo ──────────────────────────────────────────────────
st.markdown("""
<svg width='100%' viewBox='0 0 680 110' xmlns='http://www.w3.org/2000/svg'>
<style>
@keyframes scan{0%{opacity:.1}50%{opacity:.35}100%{opacity:.1}}
@keyframes pulse{0%,100%{opacity:.6}50%{opacity:1}}
.sc{animation:scan 3s ease-in-out infinite}
.pu{animation:pulse 2s ease-in-out infinite}
</style>
<rect width='680' height='110' rx='4' fill='#0a0e0a' stroke='#1a2e1a'/>
<rect width='680' height='110' rx='4' fill='none' stroke='#00ff41' stroke-width='0.5' opacity='0.25'/>
<line x1='0' y1='26' x2='680' y2='26' stroke='#00ff41' stroke-width='0.3' opacity='0.15'/>
<circle cx='16' cy='13' r='4' fill='#ff5f57'/>
<circle cx='30' cy='13' r='4' fill='#febc2e'/>
<circle cx='44' cy='13' r='4' fill='#28c840'/>
<text x='340' y='18' text-anchor='middle' font-family='monospace' font-size='9' fill='#00ff41' opacity='0.35'>sieg-monitor-energetico — pvpc-espana-tiempo-real</text>
<rect x='14' y='36' width='652' height='1' fill='#00ff41' opacity='0.06' class='sc'/>
<rect x='14' y='62' width='652' height='1' fill='#00ff41' opacity='0.06' class='sc' style='animation-delay:.8s'/>
<text x='18' y='50' font-family='monospace' font-size='9' fill='#00ff41' opacity='0.45'>root@sieg:~$</text>
<text x='100' y='50' font-family='monospace' font-size='9' fill='#00ff41'>./monitor --fuente=REE --tarifa=PVPC --modo=tiempo-real</text>
<text x='18' y='66' font-family='monospace' font-size='8' fill='#4ade80' opacity='0.65'>[+] API Red Electrica Espana | Actualizacion: cada hora | Retencion: 90 dias</text>
<text x='18' y='88' font-family='monospace' font-size='18' font-weight='bold' fill='#00ff41' letter-spacing='3'>SIEG MONITOR ENERGETICO</text>
<text x='320' y='88' font-family='monospace' font-size='11' fill='#00cc33' letter-spacing='2'>Precio Luz · PVPC · España</text>
<text x='320' y='103' font-family='monospace' font-size='9' fill='#009922' opacity='0.7'>Datos oficiales Red Electrica de España</text>
<text x='18' y='103' font-family='monospace' font-size='7' fill='#00ff41' opacity='0.3'>© 2026 M.Castillo · mybloggingnotes@gmail.com</text>
<circle cx='655' cy='50' r='6' fill='none' stroke='#00ff41' stroke-width='1' opacity='0.5'/>
<circle cx='655' cy='50' r='3' fill='#00ff41' class='pu'/>
</svg>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────
st.sidebar.markdown("""
<div style='padding:0.4rem 0 0.8rem 0; border-bottom:1px solid rgba(0,255,65,0.15); margin-bottom:0.8rem'>
    <div style='font-size:0.65rem; color:#00cc33; font-weight:600; letter-spacing:2px'>SIEG OSINT</div>
    <div style='font-size:0.95rem; font-weight:600; color:#00ff41'>Monitor Energético</div>
    <div style='font-size:0.65rem; color:#4a7a4a'>Precio Luz PVPC · España</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style='font-size:0.75rem; line-height:1.9; opacity:0.75; margin-bottom:8px'>
    <div style='font-weight:600; margin-bottom:6px; font-size:0.8rem; color:#00ff41'>🛰️ Red SIEG OSINT</div>
    <a href='https://mcasrom.github.io/sieg-osint' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>🌐 Portal SIEG OSINT</a>
    <a href='https://politica-nacional-osint.streamlit.app' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>📊 SIEG Política Nacional</a>
    <a href='https://fake-news-narrative.streamlit.app' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>📡 Narrative Radar</a>
    <a href='https://sieg-radar-electoral.streamlit.app' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>🗳️ España Vota 2026</a>
    <a href='https://sieg-ipc.streamlit.app' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>📊 Monitor IPC · Inflación</a>
    <a href='https://sieg-monitor-boe.streamlit.app' target='_blank' style='display:block; color:#4ade80; text-decoration:none; margin-bottom:4px'>📋 Monitor BOE</a>
    <a href='https://t.me/sieg_politica' target='_blank' style='display:block; color:#4ade80; text-decoration:none'>📢 Canal @sieg_politica</a>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style='text-align:center; padding:6px 0; margin-bottom:8px'>
    <a href='https://ko-fi.com/m_castillo' target='_blank'
       style='display:inline-block; background:#FF5E5B; color:white;
              font-weight:600; font-size:0.75rem; padding:6px 14px;
              border-radius:16px; text-decoration:none'>
        ☕ Buy me a coffee
    </a>
    <div style='font-size:0.65rem; opacity:0.4; margin-top:3px'>Apoya SIEG OSINT</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='font-size:0.65rem; opacity:0.35; text-align:center; font-family:monospace'>
    © 2026 M. Castillo<br>
    <a href='mailto:mybloggingnotes@gmail.com' style='color:inherit'>mybloggingnotes@gmail.com</a><br>
    Datos: Red Eléctrica de España
</div>
""", unsafe_allow_html=True)

# ── Carga de datos ────────────────────────────────────────
@st.cache_data(ttl=300)
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

df_hoy, df_stats, df_hist, df_gen, df_gen_h = cargar_datos()

# ── Tabs ──────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚡ Precio hoy",
    "📈 Histórico",
    "💡 Consejos ahorro",
    "🔋 Mix Energético",
    "📖 Guía"
])

# ── Tab 1: Precio hoy ─────────────────────────────────────
with tab1:
    st.header(f"⚡ Precio luz hoy — {date.today().strftime('%d/%m/%Y')}")

    if df_hoy.empty:
        st.info("Cargando datos... Ejecuta el pipeline primero.")
    else:
        hora_actual = datetime.now().hour
        precio_now  = df_hoy[df_hoy["hora"] == hora_actual]["precio"].values
        precio_now  = precio_now[0] if len(precio_now) > 0 else df_hoy["precio"].iloc[-1]
        precio_kwh  = round(precio_now / 1000 * 100, 4)

        precio_min  = df_hoy["precio"].min()
        hora_min    = int(df_hoy.loc[df_hoy["precio"].idxmin(), "hora"])
        precio_max  = df_hoy["precio"].max()
        hora_max    = int(df_hoy.loc[df_hoy["precio"].idxmax(), "hora"])
        precio_med  = df_hoy["precio"].mean()

        # Consejo
        if precio_now <= precio_min * 1.2:
            consejo = "🟢 PRECIO BAJO — Buen momento para lavar, cargar coche eléctrico, lavavajillas"
            color_now = "#00cc33"
        elif precio_now >= precio_max * 0.85:
            consejo = "🔴 PRECIO ALTO — Evita electrodomésticos de alta potencia"
            color_now = "#ff4444"
        else:
            consejo = "🟡 PRECIO MEDIO — Consumo normal"
            color_now = "#ffaa00"

        # KPIs
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("⚡ Ahora", f"{precio_now:.2f} €/MWh", f"{precio_kwh:.4f} €/kWh")
        c2.metric("📉 Mínimo hoy", f"{precio_min:.2f} €/MWh", f"a las {hora_min:02d}:00h")
        c3.metric("📈 Máximo hoy", f"{precio_max:.2f} €/MWh", f"a las {hora_max:02d}:00h")
        c4.metric("📊 Media hoy", f"{precio_med:.2f} €/MWh")

        st.markdown("---")
        st.markdown(f"### {consejo}")
        st.markdown("---")

        # Gráfico barras hora a hora
        df_chart = df_hoy.copy()
        df_chart["color"] = df_chart["precio"].apply(
            lambda p: "bajo" if p <= precio_min * 1.2
            else ("alto" if p >= precio_max * 0.85 else "medio")
        )
        df_chart["hora_str"] = df_chart["hora"].apply(lambda h: f"{h:02d}:00")

        color_scale = alt.Scale(
            domain=["bajo", "medio", "alto"],
            range=["#00cc33", "#ffaa00", "#ff4444"]
        )

        chart = alt.Chart(df_chart).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("hora_str:N", title="Hora", sort=None),
            y=alt.Y("precio:Q", title="€/MWh"),
            color=alt.Color("color:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("hora_str:N", title="Hora"),
                alt.Tooltip("precio:Q", title="€/MWh", format=".2f"),
                alt.Tooltip("precio_kwh:Q", title="€/kWh", format=".5f")
            ]
        ).properties(height=300, title="Precio PVPC hora a hora")

        # Línea hora actual
        linea = alt.Chart(pd.DataFrame({"hora_str": [f"{hora_actual:02d}:00"]})).mark_rule(
            color="#ffffff", strokeDash=[4, 4], opacity=0.5
        ).encode(x=alt.X("hora_str:N", sort=None))

        st.altair_chart(chart + linea, use_container_width=True)

        # Tabla resumen horas baratas
        st.subheader("🕐 Horas más baratas del día")
        df_baratas = df_hoy.nsmallest(6, "precio")[["hora", "precio", "precio_kwh"]].copy()
        df_baratas["hora"] = df_baratas["hora"].apply(lambda h: f"{h:02d}:00 - {h+1:02d}:00")
        df_baratas.columns = ["Franja horaria", "€/MWh", "€/kWh"]
        df_baratas["€/MWh"] = df_baratas["€/MWh"].round(2)
        df_baratas["€/kWh"] = df_baratas["€/kWh"].round(5)
        st.dataframe(df_baratas, use_container_width=True, hide_index=True)

# ── Tab 2: Histórico ──────────────────────────────────────
with tab2:
    st.header("📈 Histórico de precios")

    if df_hist.empty:
        st.info("Sin datos históricos disponibles.")
    else:
        df_hist["datetime"] = pd.to_datetime(df_hist["datetime"], errors="coerce")
        df_hist["fecha"]    = pd.to_datetime(df_hist["fecha"], errors="coerce")

        # Media diaria
        df_media = df_hist.groupby("fecha")["precio"].mean().reset_index()
        df_media.columns = ["fecha", "precio_medio"]

        chart_hist = alt.Chart(df_media).mark_line(point=True, color="#00cc33").encode(
            x=alt.X("fecha:T", title="Fecha"),
            y=alt.Y("precio_medio:Q", title="€/MWh (media diaria)"),
            tooltip=[
                alt.Tooltip("fecha:T", title="Fecha"),
                alt.Tooltip("precio_medio:Q", title="Media €/MWh", format=".2f")
            ]
        ).properties(height=300, title="Precio medio diario PVPC (últimos 30 días)")

        st.altair_chart(chart_hist, use_container_width=True)

        if not df_stats.empty:
            st.subheader("📊 Resumen diario")
            df_stats["fecha"] = pd.to_datetime(df_stats["fecha"], errors="coerce")
            df_show = df_stats[["fecha", "precio_min", "hora_min", "precio_max", "hora_max", "precio_med"]].copy()
            df_show.columns = ["Fecha", "Min €/MWh", "Hora min", "Max €/MWh", "Hora max", "Media €/MWh"]
            df_show["Fecha"] = df_show["Fecha"].dt.strftime("%d/%m/%Y")
            for col in ["Min €/MWh", "Max €/MWh", "Media €/MWh"]:
                df_show[col] = df_show[col].round(2)
            st.dataframe(df_show.head(15), use_container_width=True, hide_index=True)

# ── Tab 3: Consejos ───────────────────────────────────────
with tab3:
    st.header("💡 Consejos de ahorro")

    if not df_hoy.empty:
        precio_min = df_hoy["precio"].min()
        precio_max = df_hoy["precio"].max()

        horas_baratas = df_hoy[df_hoy["precio"] <= precio_min * 1.3]["hora"].tolist()
        horas_caras   = df_hoy[df_hoy["precio"] >= precio_max * 0.8]["hora"].tolist()

        franjas_baratas = ", ".join([f"{h:02d}:00" for h in sorted(horas_baratas)])
        franjas_caras   = ", ".join([f"{h:02d}:00" for h in sorted(horas_caras)])

        st.markdown(f"""
### 🟢 Horas baratas hoy
**{franjas_baratas}**

Ideal para:
- Lavadora y lavavajillas
- Carga de vehículo eléctrico
- Calentador de agua
- Horno y vitrocerámica

### 🔴 Horas caras hoy
**{franjas_caras}**

Evitar en estas horas:
- Electrodomésticos de alta potencia
- Calefacción eléctrica
- Secadora

### 📐 Tu consumo estimado
""")
        potencia = st.slider("Potencia del electrodoméstico (W)", 500, 5000, 2000, step=100)
        horas_uso = st.slider("Horas de uso", 0.5, 4.0, 1.0, step=0.5)

        precio_barato = precio_min * potencia / 1000 * horas_uso / 1000 * 100
        precio_caro   = precio_max * potencia / 1000 * horas_uso / 1000 * 100
        ahorro        = precio_caro - precio_barato

        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("💚 En hora barata", f"{precio_barato:.3f} €")
        cc2.metric("❌ En hora cara", f"{precio_caro:.3f} €")
        cc3.metric("💰 Ahorro potencial", f"{ahorro:.3f} €")

# ── Tab 4: Guía ───────────────────────────────────────────
with tab5:
    st.header("📖 Guía de uso")
    st.markdown("""
## SIEG Monitor Energético España

Seguimiento en tiempo real del precio de la electricidad PVPC en España.

### ¿Qué es el PVPC?
El Precio Voluntario para el Pequeño Consumidor es la tarifa regulada de electricidad
que varía hora a hora según el mercado mayorista. Es la tarifa más común en hogares españoles.

### Fuente de datos
- **API Red Eléctrica de España (REE)** — datos oficiales
- Actualización: cada hora automáticamente
- Retención: 90 días de histórico

### Cómo interpretar los precios
| Rango | Interpretación |
|---|---|
| 🟢 Verde | Precio bajo — buen momento para consumir |
| 🟡 Amarillo | Precio medio — consumo normal |
| 🔴 Rojo | Precio alto — minimiza el consumo |

### Red SIEG OSINT
Este monitor forma parte del ecosistema SIEG OSINT España.

---
© 2026 M. Castillo · mybloggingnotes@gmail.com ·
[Portal SIEG OSINT](https://mcasrom.github.io/sieg-osint)
    """)

# ── Tab 4: Mix Energético + Predicción ──────────────────
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

st.markdown("---")
st.markdown("""
<div style='text-align:center; font-size:0.72rem; opacity:0.35; font-family:monospace'>
    SIEG Monitor Energético · PVPC España · © 2026 M. Castillo ·
    Datos: <a href='https://www.ree.es' target='_blank' style='color:inherit'>Red Eléctrica de España</a>
</div>
""", unsafe_allow_html=True)
