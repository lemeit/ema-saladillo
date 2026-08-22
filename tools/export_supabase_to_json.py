"""
Exporta las tablas de mediciones + vistas armonizadas de EMA Saladillo desde
Supabase a archivos JSON locales, como paso previo a migrar todo a Cloudflare D1.

Solo LEE datos (no modifica ni borra nada en Supabase). Usa la misma
credencial anon que ya está hardcodeada en tools/monitor_ema.py.

Uso:
    pip install -r requirements.txt   (si no lo corriste ya)
    python tools/export_supabase_to_json.py
"""
import os
import json
import requests

SUPA_URL = "https://kpymhaixankylrzwwqge.supabase.co"
SUPA_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtweW1oYWl4YW5reWxyend3cWdlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3NDk1NjksImV4cCI6MjA4OTMyNTU2OX0."
    "Jy6msjgC0BXpHscOoWnmpD6O6Ax7OAj41PSMutKlDAY"
)

HEADERS_BASE = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
}

# Solo lo de EMA. OJO: este proyecto de Supabase es compartido con otras apps
# (hidratacion, pesos, sesiones, ritmo_*, ai_history, config) — NO tocar esas.
TABLAS = ["mediciones_ema", "mediciones_cfr", "mediciones_dc", "mediciones_cs"]
VISTAS = ["v_ema_armonizada", "v_temperatura_comparativa"]

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "migracion_d1")
os.makedirs(OUT_DIR, exist_ok=True)

PAGE_SIZE = 1000


def exportar(nombre, order_col):
    filas = []
    offset = 0
    while True:
        headers = dict(HEADERS_BASE)
        headers["Range-Unit"] = "items"
        headers["Range"] = f"{offset}-{offset + PAGE_SIZE - 1}"
        resp = requests.get(
            f"{SUPA_URL}/rest/v1/{nombre}",
            headers=headers,
            params={"order": order_col},
            timeout=30,
        )
        resp.raise_for_status()
        chunk = resp.json()
        filas.extend(chunk)
        print(f"  {nombre}: {len(filas)} filas...")
        if len(chunk) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    out_path = os.path.join(OUT_DIR, f"{nombre}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(filas, f, ensure_ascii=False)
    print(f"OK {nombre}: {len(filas)} filas exportadas -> {out_path}")


if __name__ == "__main__":
    print(f"Exportando a: {OUT_DIR}\n")
    for t in TABLAS:
        exportar(t, order_col="id")
    for v in VISTAS:
        exportar(v, order_col="hora")
    print("\nListo. Avisale a Claude que ya están los JSON en migracion_d1/.")
