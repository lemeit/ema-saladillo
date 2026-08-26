"""
monitor_ema.py
==============
Monitoreo del sistema EMA Saladillo — estado, conteo de registros,
última inserción por estación, y estimación de uso de Supabase.

Uso:
    python monitor_ema.py              # resumen general
    python monitor_ema.py --horas 24   # últimas 24 horas
    python monitor_ema.py --live       # refresca cada 60 segundos

Dependencias:
    pip install requests
"""

import requests
import json
import argparse
import time
import os
from datetime import datetime, timezone, timedelta

SUPA_URL = "https://kpymhaixankylrzwwqge.supabase.co"
SUPA_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtweW1oYWl4YW5reWxyend3cWdlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3NDk1NjksImV4cCI6MjA4OTMyNTU2OX0.Jy6msjgC0BXpHscOoWnmpD6O6Ax7OAj41PSMutKlDAY"
TZ_AR = timezone(timedelta(hours=-3))

TABLAS = [
    { "tabla": "mediciones_ema", "nombre": "EET N°1 (SNIH)",        "campo_fecha": "fecha_hora_utc", "color": "\033[94m" },
    { "tabla": "mediciones_cfr", "nombre": "CFR Saladillo",          "campo_fecha": "insertado_en",   "color": "\033[92m" },
    { "tabla": "mediciones_dc",  "nombre": "Defensa Civil",          "campo_fecha": "insertado_en",   "color": "\033[91m" },
    { "tabla": "mediciones_cs",  "nombre": "Clima Saladillo",        "campo_fecha": "insertado_en",   "color": "\033[93m" },
]

RESET  = "\033[0m"
BOLD   = "\033[1m"
MUTED  = "\033[90m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"

SUPA_LIMITE_MB = 500

def supa_get(tabla, query):
    r = requests.get(
        f"{SUPA_URL}/rest/v1/{tabla}?{query}",
        headers={
            "apikey": SUPA_KEY,
            "Authorization": f"Bearer {SUPA_KEY}",
            "Prefer": "count=exact",
        },
        timeout=15
    )
    r.raise_for_status()
    count = int(r.headers.get("content-range", "0/0").split("/")[-1] or 0)
    return r.json(), count

def supa_rpc(funcion, params={}):
    r = requests.post(
        f"{SUPA_URL}/rest/v1/rpc/{funcion}",
        headers={
            "apikey": SUPA_KEY,
            "Authorization": f"Bearer {SUPA_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(params),
        timeout=15
    )
    r.raise_for_status()
    return r.json()

def ahora_ar():
    return datetime.now(tz=TZ_AR).strftime("%d/%m/%Y %H:%M:%S")

def delta_humanizado(dt_str):
    """Convierte un timestamp ISO a '2h 15m atrás'."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        diff = datetime.now(tz=timezone.utc) - dt
        mins = int(diff.total_seconds() / 60)
        if mins < 1:   return f"{GREEN}hace unos segundos{RESET}"
        if mins < 60:  return f"{GREEN}hace {mins} min{RESET}"
        hs = mins // 60
        ms = mins % 60
        color = GREEN if hs < 2 else YELLOW if hs < 4 else RED
        return f"{color}hace {hs}h {ms:02d}m{RESET}"
    except Exception:
        return "?"

def limpiar_consola():
    os.system('cls' if os.name == 'nt' else 'clear')

def correr_monitor(horas=48):
    limpiar_consola()
    ahora = ahora_ar()

    print(f"\n{BOLD}{'═'*62}{RESET}")
    print(f"{BOLD}  MONITOR — Red EMA Saladillo{RESET}  {MUTED}{ahora}{RESET}")
    print(f"{BOLD}{'═'*62}{RESET}\n")

    total_filas = 0
    resultados  = []

    for t in TABLAS:
        try:
            # Último registro de temperatura específicamente
            param_temp = "14" if t["tabla"] == "mediciones_ema" else "Temperatura"
            campo_param = "codigo" if t["tabla"] == "mediciones_ema" else "parametro"
            datos, _ = supa_get(t["tabla"],
                f"select={t['campo_fecha']},valor"
                f"&{campo_param}=eq.{param_temp}"
                f"&order={t['campo_fecha']}.desc&limit=1")

            # Conteo total
            _, total = supa_get(t["tabla"], "select=id")

            # Registros últimas N horas
            desde = (datetime.now(tz=timezone.utc) - timedelta(hours=horas)).strftime("%Y-%m-%dT%H:%M:%SZ")
            _, recientes = supa_get(t["tabla"],
                f"select=id&{t['campo_fecha']}=gte.{desde}")

            # Conteo de horas únicas
            datos_temp, horas_count = supa_get(t["tabla"],
                f"select={t['campo_fecha']}"
                f"&{campo_param}=eq.{param_temp}"
                f"&order={t['campo_fecha']}.desc&limit={horas}")

            ultimo = datos[0] if datos else None
            ts_ultimo = ultimo.get(t["campo_fecha"], "") if ultimo else ""
            val_ultimo = f"{float(ultimo['valor']):.1f}" if ultimo and "valor" in ultimo else "?"
            delta = delta_humanizado(ts_ultimo) if ts_ultimo else f"{RED}sin datos{RESET}"

            total_filas += total

            resultados.append({
                "nombre":    t["nombre"],
                "color":     t["color"],
                "total":     total,
                "recientes": recientes,
                "horas_reg": horas_count,
                "val_ultimo":val_ultimo,
                "delta":     delta,
                "ok":        horas_count > 0,
            })

        except Exception as e:
            resultados.append({
                "nombre":    t["nombre"],
                "color":     t["color"],
                "total":     0,
                "recientes": 0,
                "horas_reg": 0,
                "val_ultimo": "?",
                "delta":     f"{RED}ERROR: {e}{RESET}",
                "ok":        False,
            })

    # ── Tabla de estado ──────────────────────────────────────────────────────
    print(f"  {'Estación':<28} {'Total':>7} {'Últ.{h}h':>8} {'Reg.temp.':>10}  {'Última inserción':<22} {'Temp.':>6}")
    print(f"  {'-'*28} {'-'*7} {'-'*8} {'-'*10}  {'-'*22} {'-'*6}")

    for r in resultados:
        estado = f"{GREEN}●{RESET}" if r["ok"] else f"{RED}●{RESET}"
        h_label = str(horas)
        print(
            f"  {estado} {r['color']}{r['nombre']:<26}{RESET}"
            f" {r['total']:>7,}"
            f" {r['recientes']:>7,} "
            f" {r['horas_reg']:>9,}  "
            f"  {r['delta']:<30}"
            f" {r['val_ultimo']:>5}°C"
        )

    # ── Estimación de uso ────────────────────────────────────────────────────
    bytes_estimados = total_filas * 210
    mb_estimados    = bytes_estimados / (1024 * 1024)
    pct             = mb_estimados / SUPA_LIMITE_MB * 100
    barra_len       = 40
    barra_llena     = int(pct / 100 * barra_len)
    color_barra     = GREEN if pct < 30 else YELLOW if pct < 70 else RED
    barra           = f"{color_barra}{'█' * barra_llena}{'░' * (barra_len - barra_llena)}{RESET}"

    print(f"\n  {BOLD}Uso estimado Supabase{RESET} (plan free: {SUPA_LIMITE_MB} MB)")
    print(f"  {barra}  {mb_estimados:.2f} MB / {SUPA_LIMITE_MB} MB  ({pct:.2f}%)")
    print(f"  {MUTED}Total filas: {total_filas:,}  ·  ~210 bytes/fila  ·  {total_filas * 210 / 1024:.0f} KB{RESET}")

    # ── Proyección ───────────────────────────────────────────────────────────
    filas_dia    = 4 * 10 * 24   # 4 estaciones × ~10 params × 24h
    mb_dia       = filas_dia * 210 / (1024 * 1024)
    dias_restantes = (SUPA_LIMITE_MB - mb_estimados) / mb_dia if mb_dia > 0 else 9999
    años_restantes = dias_restantes / 365

    print(f"\n  {BOLD}Proyección de crecimiento:{RESET}")
    print(f"  ~{filas_dia:,} filas/día · ~{mb_dia:.2f} MB/día")
    print(f"  Capacidad restante para: {YELLOW}{dias_restantes:.0f} días ({años_restantes:.1f} años){RESET}")

    # ── Tareas programadas ───────────────────────────────────────────────────
    print(f"\n  {BOLD}Tareas programadas (últimas ejecuciones):{RESET}")
    tareas = ["EMA-Saladillo", "EMA-CFR", "EMA-DC", "EMA-CS", "Supabase-Ping"]
    for tarea in tareas:
        try:
            import subprocess
            resultado = subprocess.run(
                ["powershell", "-Command",
                 f"$i=Get-ScheduledTaskInfo -TaskName '{tarea}' 2>$null; "
                 f"if($i){{'{tarea}|'+$i.LastRunTime+'|'+$i.LastTaskResult}}else{{'NOT_FOUND'}}"],
                capture_output=True, text=True, timeout=5
            )
            salida = resultado.stdout.strip()
            if salida and salida != "NOT_FOUND" and "|" in salida:
                partes = salida.split("|")
                nombre = partes[0]
                hora   = partes[1][:16] if len(partes) > 1 else "?"
                code   = partes[2].strip() if len(partes) > 2 else "?"
                estado = f"{GREEN}✔ OK{RESET}" if code == "0" else f"{RED}✖ Error ({code}){RESET}"
                print(f"    {nombre:<18} {MUTED}{hora}{RESET}  {estado}")
            else:
                print(f"    {tarea:<18} {MUTED}no encontrada{RESET}")
        except Exception:
            print(f"    {tarea:<18} {MUTED}(solo disponible en Windows){RESET}")

    print(f"\n{BOLD}{'═'*62}{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Monitor EMA Saladillo")
    parser.add_argument("--horas", type=int, default=48,
                        help="Ventana de horas recientes a analizar (default: 48)")
    parser.add_argument("--live",  action="store_true",
                        help="Refrescar automáticamente cada 60 segundos")
    args = parser.parse_args()

    if args.live:
        print("  Modo live — Ctrl+C para detener\n")
        while True:
            try:
                correr_monitor(args.horas)
                time.sleep(60)
            except KeyboardInterrupt:
                print("\n  Detenido.\n")
                break
    else:
        correr_monitor(args.horas)


if __name__ == "__main__":
    main()
