#!/usr/bin/env python3
"""
fetch_energia.py
SIEG Monitor Energético España

Descarga precios PVPC hora a hora desde API REE.
Almacena en DuckDB y exporta Parquet.

Cron: cada hora
0 * * * * cd ~/sieg-energia && source venv/bin/activate && python3 scripts/fetch_energia.py >> logs/pipeline.log 2>&1

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

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")
    print(line)

def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pvpc (
            datetime    TIMESTAMP PRIMARY KEY,
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

def fetch_pvpc(conn, fecha):
    url = (
        f"https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real"
        f"?time_trunc=hour&geo_trunc=electric_system&geo_limit=peninsular"
        f"&geo_ids=8741&start_date={fecha}T00:00&end_date={fecha}T23:59"
    )
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "SIEG-Energia/1.0"})
        r.raise_for_status()
        data    = r.json()
        valores = data["included"][0]["attributes"]["values"]

        insertados = 0
        for v in valores:
            dt_str  = v["datetime"][:19]
            precio  = v["value"]
            hora    = int(dt_str[11:13])
            conn.execute("""
                INSERT OR IGNORE INTO pvpc (datetime, fecha, hora, precio, precio_kwh)
                VALUES (?, ?, ?, ?, ?)
            """, (dt_str, str(fecha), hora, precio, round(precio / 1000, 6)))
            insertados += 1

        log(f"[REE] {insertados} valores insertados para {fecha}")
        return valores

    except Exception as e:
        log(f"[REE] Error: {e}")
        return []

def calcular_stats(conn, fecha, valores):
    if not valores:
        return

    precios = [(v["value"], int(v["datetime"][11:13])) for v in valores]
    min_p   = min(precios, key=lambda x: x[0])
    max_p   = max(precios, key=lambda x: x[0])
    med_p   = sum(p[0] for p in precios) / len(precios)
    hora_now = datetime.now().hour
    now_p    = next((p[0] for p in precios if p[1] == hora_now), precios[-1][0])

    # Consejo basado en precio actual
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

    # Últimos 30 días
    df_pvpc = conn.execute("""
        SELECT * FROM pvpc
        WHERE fecha >= CURRENT_DATE - INTERVAL 30 DAY
        ORDER BY datetime DESC
    """).df()
    df_pvpc.to_parquet(os.path.join(exp_dir, "pvpc.parquet"), index=False)

    # Stats últimos 30 días
    df_stats = conn.execute("""
        SELECT * FROM pvpc_stats
        ORDER BY fecha DESC LIMIT 30
    """).df()
    df_stats.to_parquet(os.path.join(exp_dir, "pvpc_stats.parquet"), index=False)

    # Hoy
    df_hoy = conn.execute("""
        SELECT * FROM pvpc WHERE fecha = CURRENT_DATE ORDER BY hora
    """).df()
    df_hoy.to_parquet(os.path.join(exp_dir, "pvpc_hoy.parquet"), index=False)

    log(f"[PARQUET] pvpc:{len(df_pvpc)} stats:{len(df_stats)} hoy:{len(df_hoy)}")

def main():
    log("=" * 50)
    log("SIEG Monitor Energético — Inicio")

    conn = duckdb.connect(DB_PATH)
    init_db(conn)

    hoy   = date.today()
    ayer  = hoy - timedelta(days=1)

    # Descargar hoy y ayer
    for fecha in [ayer, hoy]:
        valores = fetch_pvpc(conn, fecha)
        if valores:
            calcular_stats(conn, fecha, valores)

    # Retención 90 días
    conn.execute("DELETE FROM pvpc WHERE fecha < CURRENT_DATE - INTERVAL 90 DAY")
    conn.execute("DELETE FROM pvpc_stats WHERE fecha < CURRENT_DATE - INTERVAL 90 DAY")

    n = conn.execute("SELECT COUNT(*) FROM pvpc").fetchone()[0]
    log(f"BD: {n} registros PVPC")

    exportar_parquet(conn)
    conn.close()

    log("Monitor Energético completado")
    log("=" * 50)

if __name__ == "__main__":
    main()
