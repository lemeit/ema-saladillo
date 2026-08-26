"""
supabase_ping.py
================
Mantiene activos los proyectos Supabase haciendo una consulta
liviana cada día. Sin esto, Supabase pausa proyectos inactivos
después de 7 días en el plan gratuito.

Agregar al Programador de tareas con trigger diario:
    Programa:   python
    Argumentos: supabase_ping.py
    Carpeta:    C:\\Users\\Of. Técnica Z6\\OneDrive\\Documentos\\ema-eet1

PowerShell (ejecutar como administrador):
    $action  = New-ScheduledTaskAction -Execute "python" -Argument "supabase_ping.py" -WorkingDirectory "C:\\Users\\Of. Técnica Z6\\OneDrive\\Documentos\\ema-eet1"
    $trigger = New-ScheduledTaskTrigger -Daily -At "08:00"
    Register-ScheduledTask -TaskName "Supabase-Ping" -Action $action -Trigger $trigger -RunLevel Highest
"""

import os
import requests
import json
from datetime import datetime, timezone, timedelta

TZ_AR = timezone(timedelta(hours=-3))

# ─── Proyectos a mantener activos ─────────────────────────────────────────────
PROYECTOS = [
    {
        "nombre": "Training Hub / EMA Saladillo",
        "url":    os.environ.get("SUPA_URL", ""),
        "key":    os.environ.get("SUPA_KEY", ""),
        "tabla":  "mediciones_ema",
    },
    # Agregá acá otros proyectos Supabase si los tenés:
    # {
    #     "nombre": "Otro proyecto",
    #     "url":    "https://XXXX.supabase.co",
    #     "key":    "eyJ...",
    #     "tabla":  "alguna_tabla",
    # },
]


def ping(proyecto):
    """Hace una consulta mínima (1 fila) para mantener el proyecto activo."""
    url = f"{proyecto['url']}/rest/v1/{proyecto['tabla']}?limit=1&select=id"
    headers = {
        "apikey":        proyecto["key"],
        "Authorization": f"Bearer {proyecto['key']}",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    return resp.status_code


def main():
    ahora = datetime.now(tz=TZ_AR).strftime("%d/%m/%Y %H:%M")
    print(f"\n[{ahora}] Supabase ping —")

    todos_ok = True
    for p in PROYECTOS:
        try:
            status = ping(p)
            if status == 200:
                print(f"  ✔  {p['nombre']} — OK (HTTP 200)")
            else:
                print(f"  ⚠  {p['nombre']} — HTTP {status}")
                todos_ok = False
        except Exception as e:
            print(f"  ✖  {p['nombre']} — Error: {e}")
            todos_ok = False

    print(f"  {'Todo OK' if todos_ok else 'Revisar errores arriba'}\n")


if __name__ == "__main__":
    if not SUPA_URL or not SUPA_KEY:
        print("  ⚠  Variables SUPA_URL / SUPA_KEY no definidas — sin Supabase")

    main()
