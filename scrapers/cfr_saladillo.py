"""
cfr_saladillo.py
================
Scraper para la EMA del CFR Saladillo.
Extrae datos del HTML de https://ema.cfrsaladillo.edu.ar/
y los guarda en Supabase (tabla mediciones_cfr).

Parámetros extraídos:
  Temperatura actual      [°C]   celda 8
  Humedad actual          [%]    celda 29
  Punto de rocío          [°C]   celda 50
  Presión barométrica     [hPa]  celda 66
  Velocidad del viento    [km/h] celda 72
  Dirección del viento    [°]    celda 74
  Lluvia diaria           [mm]   celda 91
  Lluvia intensidad       [mm/h] celda 93
  Radiación solar         [W/m²] celda 113

Uso:
    python cfr_saladillo.py              # scraping + guarda en Supabase
    python cfr_saladillo.py --csv        # también exporta CSV local
    python cfr_saladillo.py --nosupa     # solo consola, sin Supabase
    python cfr_saladillo.py --loop 3600  # repite cada 1 hora

Dependencias:
    pip install requests beautifulsoup4

Proyecto: Integración EMA Saladillo — EEST N°1 "Gral. Savio"
"""

import os
import requests
import json
import csv
import re
import argparse
import time
import warnings
from datetime import datetime, timezone, timedelta
from urllib3.exceptions import InsecureRequestWarning

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("  ✖ Falta BeautifulSoup4. Instalá con: pip install beautifulsoup4")
    exit(1)

# ─── Configuración ─────────────────────────────────────────────────────────────
URL_CFR    = "https://ema.cfrsaladillo.edu.ar/"
ESTACION   = "CFR-Saladillo"
TIMEOUT    = 15

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EEST-Saladillo-script/1.0)",
    "Accept-Language": "es-AR,es;q=0.9",
}

# ─── Supabase ──────────────────────────────────────────────────────────────────
SUPA_URL   = os.environ.get("SUPA_URL", "")
SUPA_KEY   = os.environ.get("SUPA_KEY", "")
SUPA_TABLA = "mediciones_cfr"

HEADERS_SUPA = {
    "apikey":        SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=ignore-duplicates",
}

# ─── Zona horaria Argentina ────────────────────────────────────────────────────
TZ_AR = timezone(timedelta(hours=-3))

# ─── Mapa de celdas → parámetros ──────────────────────────────────────────────
# Índice de celda <td> confirmado por inspección del HTML
MAPA_CELDAS = {
    8:   {"parametro": "Temperatura",          "unidad": "°C"},
    29:  {"parametro": "Humedad",               "unidad": "%"},
    50:  {"parametro": "Punto de Rocio",        "unidad": "°C"},
    66:  {"parametro": "Presion Barometrica",   "unidad": "hPa"},
    72:  {"parametro": "Velocidad del Viento",  "unidad": "km/h"},
    74:  {"parametro": "Direccion del Viento",  "unidad": "°"},
    91:  {"parametro": "Lluvia Diaria",         "unidad": "mm"},
    93:  {"parametro": "Intensidad Lluvia",     "unidad": "mm/h"},
    113: {"parametro": "Radiacion Solar",       "unidad": "W/m2"},
}

# ─── Helpers ───────────────────────────────────────────────────────────────────
def limpiar_valor(texto):
    """
    Extrae el número de un string como '12.1 °C', '94 %', 'S (185)'.
    Para dirección del viento devuelve los grados entre paréntesis.
    Devuelve (valor_numerico_o_None, texto_original_limpio).
    """
    texto = texto.strip()
    # Reemplazar caracteres mal encodados
    texto = texto.replace("°", "°").replace("Â°", "°").replace("â€°", "°")
    texto = " ".join(texto.split())  # normalizar espacios

    # Dirección del viento: "S (185)" → 185
    m = re.search(r'\((\d+\.?\d*)\)', texto)
    if m:
        return float(m.group(1)), texto

    # Número con posible decimal
    m = re.search(r'-?\d+\.?\d*', texto)
    if m:
        return float(m.group()), texto

    return None, texto


def ahora_ar():
    return datetime.now(tz=TZ_AR).strftime("%d/%m/%Y %H:%M")


# ─── Scraping ──────────────────────────────────────────────────────────────────
def obtener_datos_cfr():
    """
    Descarga el HTML del CFR y extrae los parámetros por índice de celda.
    Devuelve lista de dicts con parametro, unidad, valor, valor_texto, fecha_hora_ar.
    """
    resp = requests.get(URL_CFR, headers=HEADERS, timeout=TIMEOUT, verify=False)
    resp.raise_for_status()

    # El HTML usa windows-1252 — forzar encoding correcto
    resp.encoding = "windows-1252"
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    celdas = soup.find_all("td")

    # Extraer fecha y hora de la página
    fecha_pag = ""
    hora_pag  = ""
    for i, td in enumerate(celdas):
        txt = td.get_text(strip=True)
        if "FECHA:" in txt:
            fecha_pag = txt.replace("FECHA:", "").strip()
        if "HORA:" in txt:
            hora_pag = txt.replace("HORA:", "").strip()

    fecha_hora = f"{fecha_pag} {hora_pag}".strip() or ahora_ar()

    resultados = []
    for idx, meta in MAPA_CELDAS.items():
        if idx >= len(celdas):
            continue
        texto_celda = celdas[idx].get_text(separator=" ", strip=True)
        valor_num, texto_limpio = limpiar_valor(texto_celda)

        resultados.append({
            "estacion":      ESTACION,
            "parametro":     meta["parametro"],
            "unidad":        meta["unidad"],
            "valor":         valor_num,
            "valor_texto":   texto_limpio,
            "fecha_hora_ar": fecha_hora,
        })

    return resultados


# ─── Supabase ──────────────────────────────────────────────────────────────────
def guardar_en_supabase(datos):
    """Inserta los datos en mediciones_cfr. Ignora duplicados."""
    filas = [d for d in datos if d["valor"] is not None]
    if not filas:
        return 0

    url  = f"{SUPA_URL}/rest/v1/{SUPA_TABLA}"
    resp = requests.post(url, headers=HEADERS_SUPA,
                         data=json.dumps(filas), timeout=15)
    if resp.status_code in (200, 201):
        return len(filas)
    elif resp.status_code == 409:
        return 0
    else:
        raise RuntimeError(f"Supabase HTTP {resp.status_code}: {resp.text[:200]}")


# ─── Consola ───────────────────────────────────────────────────────────────────
def mostrar_consola(datos, insertados=None):
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║   EMA CFR Saladillo                                  ║")
    print(f"║   Consulta: {ahora_ar()}                            ║")
    print("║   Davis Instruments · ema.cfrsaladillo.edu.ar        ║")
    print("╠══════════════════════════════════════════════════════╣")
    for d in datos:
        val = f"{d['valor']:.1f} {d['unidad']}" if d['valor'] is not None else "Sin dato"
        print(f"║  {d['parametro']:<28} {val:<14}  {d['fecha_hora_ar']}  ║")
    print("╠══════════════════════════════════════════════════════╣")
    if insertados is not None:
        if insertados > 0:
            print(f"║  Supabase: {insertados} filas insertadas ✔                      ║")
        else:
            print(f"║  Supabase: sin cambios (datos ya existían)               ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()


# ─── CSV ───────────────────────────────────────────────────────────────────────
def exportar_csv(datos, archivo="cfr_actuales.csv"):
    with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
        campos = ["estacion","parametro","unidad","valor","valor_texto","fecha_hora_ar"]
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(datos)
    print(f"  ✔  CSV → {archivo}")


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="EMA CFR Saladillo → Supabase")
    parser.add_argument("--csv",    action="store_true", help="Exportar CSV")
    parser.add_argument("--nosupa", action="store_true", help="No guardar en Supabase")
    parser.add_argument("--loop",   type=int, default=0,
                        help="Repetir cada N segundos (ej: --loop 3600)")
    args = parser.parse_args()

    def ciclo():
        try:
            datos = obtener_datos_cfr()

            insertados = None
            if not args.nosupa:
                try:
                    insertados = guardar_en_supabase(datos)
                except Exception as e:
                    print(f"  ⚠  Supabase: {e}")

            mostrar_consola(datos, insertados)

            if args.csv:
                exportar_csv(datos)

        except requests.HTTPError as e:
            print(f"\n  ✖ Error HTTP: {e}")
        except requests.ConnectionError as e:
            print(f"\n  ✖ Sin conexión a {URL_CFR}: {e}")
        except Exception as e:
            print(f"\n  ✖ Error inesperado: {e}")

    if args.loop > 0:
        print(f"  Modo automático — cada {args.loop//60} min. Ctrl+C para detener.\n")
        while True:
            ciclo()
            time.sleep(args.loop)
    else:
        ciclo()


if __name__ == "__main__":
    if not SUPA_URL or not SUPA_KEY:
        print("  ⚠  Variables SUPA_URL / SUPA_KEY no definidas — sin Supabase")

    main()
