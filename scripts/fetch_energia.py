#!/usr/bin/env python3
"""
fetch_energia.py
SIEG Monitor Energético España v2.0

Descarga:
- Precios PVPC hora a hora (REE)
- Mix de generación por fuente (REE)
- % Renovable vs No renovable

Cron: cada hora a :08
8 * * * * cd ~/sieg-energia && source venv/bin/activate && python3 scripts/fetch_energia.py >> logs/pipeline.log 2>&1 && git add data/exports/ && git commit -m "auto: energia $(date +%Y-%m-%d-%H)" && git push origin main 2>/dev/null

Autor : M. Castillo · mybloggingnotes@gmail.com
© 2026 M. Castillo
"""

import os
import requests
import duckdb
from datetime import datetime, date, timedelta

BASE_DIR = os.path.expanduser("~/sieg-energia")
DB_PATH  = os.path.join(BASE_DIR, "data", "processed", "energia.duckdb")
LOG_PATH = os.path.join(BASE_DIR, "logs", "pipeline.log")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

# Colores por fuente para el dashboard
COLORES_FUENTE = {
    "Nuclear":              "#f59e0b",
    "Hidráulica":           "#3b82f6",
    "Eólica":               "#10b981",
    "Solar fotovoltaica":   "#fbbf24",
    "Solar térmica":        "#f97316",
    "Ciclo combinado":      "#ef4444",
    "Carbón":               "#6b7280",
    "Cogeneración":         "#8b5cf6",
    "Otras renovables":     "#06b6d4",
    "Residuos renovables":  "#84cc16",
    "Residuos no renovables":"#dc2626",
    "Turbina de vapor":     "#f43f5e",
}

RENOVABLES = {
    "Hidráulica", "Eólica", "Solar fotovoltaica",
    "Solar térmica", "Otras renovables", "Residuos renovables"
}

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")
    print(line)

def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pvpc (
            datetime    VARCHAR PRIMARY KEY,
            fecha       DATE,
            hora        INTEGER,
            precio      DOUBLE,
            precio_kwh  DOUBLE,
            ingestion_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pvpc_stats (
            fecha       DATE PRIMARY KEY,
            precio_min  DOUBLE,
            hora_min    INTEGER,
            precio_max  DOUBLE,
            hora_max    INTEGER,
            precio_med  DOUBLE,
            precio_now  DOUBLE,
            hora_now    INTEGER,
            consejo     VARCHAR,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generacion (
            fecha       DATE,
            fuente      VARCHAR,
            valor_mwh   DOUBLE,
            es_renovable BOOLEAN,
            color       VARCHAR,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (fecha, fuente)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generacion_hora (
            datetime    VARCHAR,
            fecha       DATE,
            hora        INTEGER,
            fuente      VARCHAR,
            valor_mwh   DOUBLE,
            es_renovable BOOLEAN,
            PRIMARY KEY (datetime, fuente)
        )
    """)

def fetch_pvpc(conn, fecha):
    url = (
        f"https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real"
        f"?time_trunc=hour&geo_trunc=electric_system&geo_limit=peninsular"
        f"&geo_ids=8741&start_date={fecha}T00:00&end_date={fecha}T23:59"
    )
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "SIEG-Energia/2.0"})
        r.raise_for_status()
        data    = r.json()
        valores = data["included"][0]["attributes"]["values"]

        for v in valores:
            dt_str = v["datetime"][:19]
            precio = v["value"]
            hora   = int(dt_str[11:13])
            conn.execute("""
                INSERT OR IGNORE INTO pvpc (datetime, fecha, hora, precio, precio_kwh)
                VALUES (?, ?, ?, ?, ?)
            """, (dt_str, str(fecha), hora, precio, round(precio / 1000, 6)))

        log(f"[PVPC] {len(valores)} valores para {fecha}")
        return valores
    except Exception as e:
        log(f"[PVPC] Error: {e}")
        return []

def fetch_generacion(conn, fecha):
    """Descarga mix de generación por fuente."""
    url = (
        f"https://apidatos.ree.es/es/datos/generacion/estructura-generacion"
        f"?time_trunc=day&geo_trunc=electric_system&geo_limit=peninsular"
        f"&geo_ids=8741&start_date={fecha}T00:00&end_date={fecha}T23:59"
    )
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "SIEG-Energia/2.0"})
        r.raise_for_status()
        data = r.json()

        insertados = 0
        for item in data.get("included", []):
            fuente = item["type"]
            if fuente == "Generación total":
                continue
            vals = item["attributes"].get("values", [])
            if not vals:
                continue
            valor = vals[-1]["value"]
            es_ren = fuente in RENOVABLES
            color  = COLORES_FUENTE.get(fuente, "#888888")

            conn.execute("""
                INSERT OR REPLACE INTO generacion
                (fecha, fuente, valor_mwh, es_renovable, color)
                VALUES (?, ?, ?, ?, ?)
            """, (str(fecha), fuente, valor, es_ren, color))
            insertados += 1

        log(f"[GEN] {insertados} fuentes para {fecha}")
        return insertados
    except Exception as e:
        log(f"[GEN] Error: {e}")
        return 0

def fetch_generacion_hora(conn, fecha):
    """Descarga mix de generación hora a hora."""
    url = (
        f"https://apidatos.ree.es/es/datos/generacion/estructura-generacion"
        f"?time_trunc=hour&geo_trunc=electric_system&geo_limit=peninsular"
        f"&geo_ids=8741&start_date={fecha}T00:00&end_date={fecha}T23:59"
    )
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "SIEG-Energia/2.0"})
        r.raise_for_status()
        data = r.json()

        insertados = 0
        for item in data.get("included", []):
            fuente = item["type"]
            if fuente == "Generación total":
                continue
            es_ren = fuente in RENOVABLES
            for v in item["attributes"].get("values", []):
                dt_str = v["datetime"][:19]
                hora   = int(dt_str[11:13])
                conn.execute("""
                    INSERT OR IGNORE INTO generacion_hora
                    (datetime, fecha, hora, fuente, valor_mwh, es_renovable)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (dt_str, str(fecha), hora, fuente, v["value"], es_ren))
                insertados += 1

        log(f"[GEN_H] {insertados} registros hora a hora para {fecha}")
        return insertados
    except Exception as e:
        log(f"[GEN_H] Error: {e}")
        return 0

def calcular_stats(conn, fecha, valores):
    if not valores:
        return
    precios  = [(v["value"], int(v["datetime"][11:13])) for v in valores]
    min_p    = min(precios, key=lambda x: x[0])
    max_p    = max(precios, key=lambda x: x[0])
    med_p    = sum(p[0] for p in precios) / len(precios)
    hora_now = datetime.now().hour
    now_p    = next((p[0] for p in precios if p[1] == hora_now), precios[-1][0])

    if now_p <= min_p[0] * 1.2:
        consejo = "🟢 PRECIO BAJO — Buen momento para lavar, cargar coche, etc."
    elif now_p >= max_p[0] * 0.85:
        consejo = "🔴 PRECIO ALTO — Evita electrodomésticos de alta potencia"
    else:
        consejo = "🟡 PRECIO MEDIO — Consumo normal"

    conn.execute("""
        INSERT OR REPLACE INTO pvpc_stats
        (fecha, precio_min, hora_min, precio_max, hora_max, precio_med, precio_now, hora_now, consejo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(fecha), min_p[0], min_p[1], max_p[0], max_p[1],
          round(med_p, 2), now_p, hora_now, consejo))

def exportar_parquet(conn):
    import pandas as pd
    exp_dir = os.path.join(BASE_DIR, "data", "exports")
    os.makedirs(exp_dir, exist_ok=True)

    exportaciones = {
        "pvpc":         "SELECT * FROM pvpc WHERE fecha >= CURRENT_DATE - INTERVAL 30 DAY ORDER BY datetime DESC",
        "pvpc_hoy":     "SELECT * FROM pvpc WHERE fecha = CURRENT_DATE ORDER BY hora",
        "pvpc_stats":   "SELECT * FROM pvpc_stats ORDER BY fecha DESC LIMIT 30",
        "generacion":   "SELECT * FROM generacion WHERE fecha >= CURRENT_DATE - INTERVAL 30 DAY ORDER BY fecha DESC, valor_mwh DESC",
        "gen_hoy":      "SELECT * FROM generacion WHERE fecha = CURRENT_DATE ORDER BY valor_mwh DESC",
        "gen_hora_hoy": "SELECT * FROM generacion_hora WHERE fecha = CURRENT_DATE ORDER BY hora, fuente",
    }

    for nombre, query in exportaciones.items():
        try:
            df = conn.execute(query).df()
            df.to_parquet(os.path.join(exp_dir, f"{nombre}.parquet"), index=False)
            log(f"[PARQUET] {nombre}: {len(df)} filas")
        except Exception as e:
            log(f"[PARQUET] Error {nombre}: {e}")

def main():
    log("=" * 50)
    log("SIEG Monitor Energético v2.0 — Inicio")

    conn = duckdb.connect(DB_PATH)
    init_db(conn)

    hoy  = date.today()
    ayer = hoy - timedelta(days=1)

    for fecha in [ayer, hoy]:
        valores = fetch_pvpc(conn, fecha)
        if valores:
            calcular_stats(conn, fecha, valores)
        fetch_generacion(conn, fecha)
        fetch_generacion_hora(conn, fecha)

    # Retención 90 días
    for tabla in ["pvpc", "pvpc_stats", "generacion", "generacion_hora"]:
        conn.execute(f"DELETE FROM {tabla} WHERE fecha < CURRENT_DATE - INTERVAL 90 DAY")

    n_pvpc = conn.execute("SELECT COUNT(*) FROM pvpc").fetchone()[0]
    n_gen  = conn.execute("SELECT COUNT(*) FROM generacion").fetchone()[0]
    log(f"BD: {n_pvpc} pvpc · {n_gen} generacion")

    exportar_parquet(conn)
    conn.close()

    log("Monitor Energético v2.0 completado")
    log("=" * 50)

if __name__ == "__main__":
    main()
