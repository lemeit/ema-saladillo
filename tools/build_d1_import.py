"""
Convierte los JSON exportados de Supabase (mediciones_ema/cfr/dc/cs) en un
único archivo SQL para cargar en Cloudflare D1, en la tabla unificada
`mediciones`.

- Normaliza el código de estación a EMA-EET / EMA-CFR / EMA-DC / EMA-CS.
- Calcula fecha_hora_utc en formato 'YYYY-MM-DD HH:MM:SS' (UTC, sin sufijo,
  mismo formato que ya usa purpleair-saladillo en D1) a partir de
  fecha_hora_utc cuando existe (mediciones_ema) o de fecha_hora_ar
  (hora Argentina, UTC-3) para cfr/dc/cs.
- Genera INSERTs en lotes para no pasarnos de tamaño por archivo.

Uso:
    python tools/build_d1_import.py
Genera:
    migracion_d1/schema.sql
    migracion_d1/import_mediciones.sql
"""
import json
import os
import re
from datetime import datetime, timedelta

BASE = os.path.join(os.path.dirname(__file__), "..", "migracion_d1")

FUENTES = {
    "mediciones_ema": "EMA-EET",
    "mediciones_cfr": "EMA-CFR",
    "mediciones_dc": "EMA-DC",
    "mediciones_cs": "EMA-CS",
}

BATCH = 200


def parse_ar_a_utc(fecha_ar):
    """'21/03/2026 23:28' o '21/03/26 22:30' (hora Argentina) -> 'YYYY-MM-DD HH:MM:SS' UTC"""
    fecha_ar = fecha_ar.strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            dt_ar = datetime.strptime(fecha_ar, fmt)
            dt_utc = dt_ar + timedelta(hours=3)  # Argentina = UTC-3, sin horario de verano
            return dt_utc.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def parse_iso_a_utc(fecha_iso):
    """'2026-03-22T00:00:00+00:00' -> '2026-03-22 00:00:00'"""
    fecha_iso = fecha_iso.strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})", fecha_iso)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return None


def sql_str(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def sql_num(v):
    if v is None or v == "":
        return "NULL"
    try:
        return repr(float(v))
    except (ValueError, TypeError):
        return "NULL"


def convertir_tabla(nombre_archivo, estacion_codigo):
    path = os.path.join(BASE, f"{nombre_archivo}.json")
    filas = json.load(open(path, encoding="utf-8"))
    out_rows = []
    sin_fecha = 0
    for r in filas:
        if r.get("fecha_hora_utc"):
            fecha = parse_iso_a_utc(r["fecha_hora_utc"])
        else:
            fecha = parse_ar_a_utc(r.get("fecha_hora_ar", ""))
        if not fecha:
            sin_fecha += 1
            continue
        out_rows.append(
            (
                estacion_codigo,
                r.get("codigo"),
                r.get("parametro"),
                r.get("unidad"),
                r.get("valor"),
                r.get("valor_texto"),
                fecha,
            )
        )
    print(f"{nombre_archivo}: {len(out_rows)} filas convertidas, {sin_fecha} descartadas por fecha inválida")
    return out_rows


def main():
    todas = []
    for archivo, codigo in FUENTES.items():
        todas.extend(convertir_tabla(archivo, codigo))

    print(f"\nTotal a importar: {len(todas)} filas")

    out_path = os.path.join(BASE, "import_mediciones.sql")
    with open(out_path, "w", encoding="utf-8") as f:
        for i in range(0, len(todas), BATCH):
            lote = todas[i : i + BATCH]
            valores = []
            for (estacion, codigo, parametro, unidad, valor, valor_texto, fecha) in lote:
                valores.append(
                    "("
                    + ", ".join(
                        [
                            sql_str(estacion),
                            str(codigo) if codigo is not None else "NULL",
                            sql_str(parametro),
                            sql_str(unidad),
                            sql_num(valor),
                            sql_str(valor_texto),
                            sql_str(fecha),
                        ]
                    )
                    + ")"
                )
            f.write(
                "INSERT INTO mediciones (estacion, codigo, parametro, unidad, valor, valor_texto, fecha_hora_utc) VALUES\n"
                + ",\n".join(valores)
                + ";\n\n"
            )

    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
