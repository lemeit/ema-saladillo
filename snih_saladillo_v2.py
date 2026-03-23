"""
snih_saladillo_v2.py
====================
Obtiene datos en tiempo real de la EMA Saladillo desde el SNIH.

Estación: 284094  (red RMET=28 + ID=4094)
Sitio:    https://snih.hidricosargentina.gob.ar
Endpoint: MuestraDatos.aspx/LeerDatosActuales  (POST JSON)

Parámetros confirmados en esta estación:
  Codigo  Nombre
     4    Velocidad del Viento        [km/h]
     5    Dirección del Viento        [°]
    14    Temperatura Bulbo Seco      [°C]
    18    Humedad                     [%]
    20    Precipitación               [mm]  (acumulada desde medianoche)
   218    Presión Atmosférica         [mBar]
  9998    Precipitación Instantánea   [mm]

Uso:
    python snih_saladillo_v2.py              # muestra datos en consola
    python snih_saladillo_v2.py --csv        # exporta a CSV
    python snih_saladillo_v2.py --json       # muestra JSON crudo
    python snih_saladillo_v2.py --loop 300   # refresca cada 300 segundos

Dependencias:
    pip install requests

Proyecto: Integración sensores calidad del aire
          Laboratorio de Industrias 7° Año — EEST N°1 "Gral. Savio" — Saladillo
Fuente:   SNIH / INA — datos sin validar — citar la fuente al publicar
"""

import requests
import json
import csv
import argparse
import time
import warnings
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime, timezone, timedelta

# ─── Configuración ─────────────────────────────────────────────────────────────
ESTACION      = "284094"          # red RMET (28) + ID estación (4094)
URL_ACTUALES  = "https://snih.hidricosargentina.gob.ar/MuestraDatos.aspx/LeerDatosActuales"
URL_ULTIMOS   = "https://snih.hidricosargentina.gob.ar/MuestraDatos.aspx/LeerUltimosRegistros"
TIMEOUT       = 15

# El certificado SSL del SNIH está vencido (problema del servidor, no nuestro).
# verify=False le dice a requests que iguale el comportamiento del navegador.
warnings.filterwarnings("ignore", category=InsecureRequestWarning)
SSL_VERIFY = False

HEADERS = {
    "Content-Type":    "application/json; charset=utf-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer":         "https://snih.hidricosargentina.gob.ar/MuestraDatos.aspx",
    "User-Agent":      "Mozilla/5.0 (compatible; EEST-Saladillo-script/2.0)",
}

# Zona horaria Argentina (UTC-3, sin cambio de horario)
TZ_AR = timezone(timedelta(hours=-3))

# Metadatos de cada parámetro: nombre para mostrar + unidad + decimales
PARAMETROS = {
    4:    {"nombre": "Velocidad del Viento",      "unidad": "km/h",  "dec": 1},
    5:    {"nombre": "Dirección del Viento",       "unidad": "°",     "dec": 0, "rosa": True},
    14:   {"nombre": "Temperatura",               "unidad": "°C",    "dec": 1},
    18:   {"nombre": "Humedad",                   "unidad": "%",     "dec": 0},
    20:   {"nombre": "Precipitación (acum.)",      "unidad": "mm",    "dec": 2},
    218:  {"nombre": "Presión Atmosférica",        "unidad": "mBar",  "dec": 1},
    9998: {"nombre": "Precipitación Instantánea", "unidad": "mm",    "dec": 2},
}


# ─── Conversión de fechas ──────────────────────────────────────────────────────
def parse_fecha(fecha_str):
    """
    Convierte '/Date(1774134000000)/' (milisegundos UTC desde epoch)
    a datetime con zona horaria de Argentina.
    """
    try:
        ms = int(fecha_str.replace("/Date(", "").replace(")/", ""))
        dt_utc = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt_utc.astimezone(TZ_AR)
    except Exception:
        return None

def formato_fecha(dt):
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M")


# ─── Rosa de los vientos ───────────────────────────────────────────────────────
def grados_a_rosa(grados):
    """Convierte grados a punto cardinal (16 rumbos)."""
    puntos = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
              "S","SSO","SO","OSO","O","ONO","NO","NNO"]
    idx = round(grados / 22.5) % 16
    return puntos[idx]


# ─── Llamada al endpoint ───────────────────────────────────────────────────────
def obtener_datos_actuales():
    """
    POST a LeerDatosActuales → devuelve lista de mediciones o lanza excepción.
    """
    payload = json.dumps({"estacion": ESTACION})
    resp = requests.post(URL_ACTUALES, data=payload, headers=HEADERS, timeout=TIMEOUT, verify=SSL_VERIFY)
    resp.raise_for_status()
    resultado = resp.json()

    d = resultado.get("d", {})
    if not d.get("RespuestaOK", False):
        raise RuntimeError(f"El servidor devolvió error: {d.get('MsgErr','sin detalle')}")

    mediciones = d.get("Mediciones", [])
    if not mediciones:
        raise RuntimeError("El servidor respondió OK pero Mediciones está vacío.")

    return mediciones


def obtener_ultimos_registros(codigo_parametro, fecha_desde, fecha_hasta):
    """
    POST a LeerUltimosRegistros para un parámetro y rango de fechas.
    fecha_desde / fecha_hasta: strings 'YYYY-MM-DD'
    """
    payload = json.dumps({
        "fechaDesde": fecha_desde,
        "fechaHasta": fecha_hasta,
        "estacion":   ESTACION,
        "codigo":     str(codigo_parametro),
    })
    resp = requests.post(URL_ULTIMOS, data=payload, headers=HEADERS, timeout=TIMEOUT, verify=SSL_VERIFY)
    resp.raise_for_status()
    resultado = resp.json()
    d = resultado.get("d", {})
    if not d.get("RespuestaOK", False):
        raise RuntimeError(d.get("MsgErr", "sin detalle"))
    return d.get("Mediciones", [])


# ─── Formateo de salida ────────────────────────────────────────────────────────
def formatear_valor(medicion):
    """Devuelve el valor como string con unidad, respetando decimales."""
    codigo = medicion["Codigo"]
    valor  = medicion["Valor"]
    meta   = PARAMETROS.get(codigo, {"unidad": "?", "dec": 2})

    if valor < -998:
        return "Sin dato"

    valor_str = f"{valor:.{meta['dec']}f}"

    # Para dirección del viento mostramos grados Y rumbo
    if meta.get("rosa"):
        return f"{valor_str}° ({grados_a_rosa(valor)})"

    return f"{valor_str} {meta['unidad']}"


def mostrar_consola(mediciones):
    ahora_ar = datetime.now(tz=TZ_AR).strftime("%d/%m/%Y %H:%M")
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║   EMA Saladillo — EEST N°1 'Gral. Savio'            ║")
    print(f"║   Estación {ESTACION}  |  Consulta: {ahora_ar}      ║")
    print("║   Red Meteorológica RMET — SNIH/INA — Sin validar   ║")
    print("╠══════════════════════════════════════════════════════╣")

    for m in mediciones:
        codigo = m["Codigo"]
        meta   = PARAMETROS.get(codigo, {"nombre": m.get("NombreCodigo", f"Cod {codigo}")})
        nombre = meta["nombre"]
        valor  = formatear_valor(m)
        fecha  = formato_fecha(parse_fecha(m["FechaHora"]))
        print(f"║  {nombre:<28} {valor:<14}  {fecha}  ║")

    print("╚══════════════════════════════════════════════════════╝")
    print()


# ─── Exportar CSV ──────────────────────────────────────────────────────────────
def exportar_csv(mediciones, archivo="saladillo_actuales.csv"):
    filas = []
    for m in mediciones:
        codigo = m["Codigo"]
        meta   = PARAMETROS.get(codigo, {"nombre": m.get("NombreCodigo","?"), "unidad":"?", "dec":2})
        valor  = m["Valor"]
        dt     = parse_fecha(m["FechaHora"])
        filas.append({
            "estacion":      ESTACION,
            "codigo":        codigo,
            "parametro":     meta["nombre"],
            "unidad":        meta.get("unidad","?"),
            "valor":         "" if valor < -998 else round(valor, meta.get("dec",2)),
            "fecha_hora_ar": formato_fecha(dt),
            "fecha_hora_utc": dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else "",
        })

    with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
        campos = ["estacion","codigo","parametro","unidad","valor","fecha_hora_ar","fecha_hora_utc"]
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)

    print(f"  ✔  {len(filas)} registros exportados → {archivo}")


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Obtiene datos actuales de la EMA Saladillo (SNIH/RMET)"
    )
    parser.add_argument("--csv",  action="store_true", help="Exportar a CSV")
    parser.add_argument("--json", action="store_true", help="Mostrar JSON crudo")
    parser.add_argument("--loop", type=int, default=0,
                        help="Refrescar automáticamente cada N segundos (ej: --loop 300)")
    args = parser.parse_args()

    def ciclo():
        try:
            mediciones = obtener_datos_actuales()

            if args.json:
                print(json.dumps(mediciones, indent=2, ensure_ascii=False))
                return

            mostrar_consola(mediciones)

            if args.csv:
                exportar_csv(mediciones)

        except requests.HTTPError as e:
            print(f"\n  ✖ Error HTTP: {e}")
        except requests.ConnectionError as e:
            if "SSL" in str(e) or "certificate" in str(e).lower():
                print("\n  ✖ Error SSL — certificado del servidor vencido (problema del SNIH, no tuyo)")
                print("    El script ya tiene verify=False para saltearlo. Revisá que SSL_VERIFY = False en el código.")
            else:
                print("\n  ✖ Sin conexión — verificá el acceso a snih.hidricosargentina.gob.ar")
        except RuntimeError as e:
            print(f"\n  ✖ {e}")
        except Exception as e:
            print(f"\n  ✖ Error inesperado: {e}")

    if args.loop > 0:
        print(f"  Modo automático — actualizando cada {args.loop} segundos. Ctrl+C para detener.")
        while True:
            ciclo()
            time.sleep(args.loop)
    else:
        ciclo()


if __name__ == "__main__":
    main()
