"""
d1_writer.py
============
Helper compartido por los 4 scrapers de EMA Saladillo: inserta las
mediciones en la tabla unificada `mediciones` de Cloudflare D1, vía la
API HTTP de Cloudflare (mismo patrón que usa
purpleair-saladillo/ingest_purpleair.py para calidad del aire).

Reemplaza a guardar_en_supabase(): antes cada scraper escribía en su
propia tabla de Supabase (mediciones_ema/cfr/dc/cs); ahora todos escriben
acá, en D1, que es lo que sirve emas.lemeit.ar a través del Worker
ema-saladillo-api.

Variables de entorno requeridas (se cargan como secrets en GitHub Actions):
    CF_ACCOUNT_ID   -> Account ID de Cloudflare
    CF_DATABASE_ID  -> database_id de ema-saladillo-db
                       (b5b1eef7-5c8d-42a8-a23e-69cd5ae1cd30)
    CF_API_TOKEN    -> API token de Cloudflare con permiso D1:Edit

Requiere el índice único idx_mediciones_dedup sobre
(estacion, parametro, fecha_hora_utc) — ver d1/schema.sql — para que
"INSERT OR IGNORE" no duplique filas si un scraper se reintenta o si el
cron se superpone con una corrida manual.
"""

import os
import requests
from datetime import datetime, timezone, timedelta

CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_DATABASE_ID = os.environ.get("CF_DATABASE_ID", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")

D1_URL = (
    f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}"
    f"/d1/database/{CF_DATABASE_ID}/query"
)

TZ_AR = timezone(timedelta(hours=-3))

INSERT_SQL = """
    INSERT OR IGNORE INTO mediciones
        (estacion, codigo, parametro, unidad, valor, valor_texto, fecha_hora_utc)
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""


def _fecha_ar_a_utc(fecha_ar):
    """'DD/MM/YYYY HH:MM' (hora Argentina, UTC-3 fijo) -> 'YYYY-MM-DD HH:MM:SS' (UTC)."""
    dt_local = datetime.strptime(fecha_ar.strip(), "%d/%m/%Y %H:%M").replace(tzinfo=TZ_AR)
    return dt_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _normalizar_fecha_utc(valor):
    """Acepta 'YYYY-MM-DDTHH:MM:SSZ' o 'YYYY-MM-DD HH:MM:SS' y devuelve el segundo formato."""
    return valor.strip().replace("T", " ").rstrip("Z")


def _d1_query(sql, params_list):
    if not (CF_ACCOUNT_ID and CF_DATABASE_ID and CF_API_TOKEN):
        raise RuntimeError(
            "Faltan variables CF_ACCOUNT_ID / CF_DATABASE_ID / CF_API_TOKEN (D1)"
        )
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        D1_URL, headers=headers, json={"sql": sql, "params": params_list}, timeout=30
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("success"):
        raise RuntimeError(f"D1 query failed: {result}")
    return result


def guardar_en_d1(estacion_d1, filas):
    """
    Inserta `filas` en la tabla unificada `mediciones` de D1.

    estacion_d1: código canónico de la estación en D1
                 ('EMA-EET' | 'EMA-CFR' | 'EMA-DC' | 'EMA-CS')
    filas: lista de dicts, cada uno con:
        codigo        (int, opcional — solo EMA-EET)
        parametro     (str, requerido)
        unidad        (str, opcional)
        valor         (float, requerido — filas sin valor se descartan)
        valor_texto   (str, opcional)
        fecha_hora_utc (str) o fecha_hora_ar (str 'DD/MM/YYYY HH:MM') — se
                        requiere al menos uno de los dos.

    Devuelve la cantidad de filas enviadas a D1 (no necesariamente
    insertadas: INSERT OR IGNORE descarta duplicados en silencio).
    """
    if not filas:
        return 0

    enviados = 0
    for f in filas:
        if f.get("valor") is None:
            continue

        fecha_utc = f.get("fecha_hora_utc")
        if fecha_utc:
            fecha_utc = _normalizar_fecha_utc(fecha_utc)
        else:
            fecha_ar = f.get("fecha_hora_ar")
            if not fecha_ar or fecha_ar == "—":
                continue
            try:
                fecha_utc = _fecha_ar_a_utc(fecha_ar)
            except ValueError:
                continue

        params = [
            estacion_d1,
            f.get("codigo"),
            f["parametro"],
            f.get("unidad"),
            float(f["valor"]),
            f.get("valor_texto"),
            fecha_utc,
        ]
        _d1_query(INSERT_SQL, params)
        enviados += 1

    return enviados
