"""
test_ocr_dc2.py
===============
Diagnóstico visual del preprocesamiento OCR para Defensa Civil.
Guarda imágenes intermedias para inspección.

Uso:
    python test_ocr_dc2.py

Genera archivos en el directorio actual:
    dc_original.jpg     — imagen original
    dc_bloque_XX.png    — cada bloque recortado
    dc_final.png        — imagen final que ve Tesseract
    dc_resultado.txt    — texto OCR extraído
"""

import requests
import pytesseract
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from io import BytesIO

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
URL_CAM = "https://content.meteobridge.com/cam/791751a5ea5fe89561a11d743920c3ef/camplus.jpg"

print("Descargando imagen...")
r = requests.get(URL_CAM, timeout=15)
img = Image.open(BytesIO(r.content))
w, h = img.size
print(f"Tamaño: {w}x{h}")
img.save("dc_original.jpg")
print("Guardada: dc_original.jpg")

# ── Coordenadas de bloques (calibradas para 1800x1013) ──────────────────────
sx, sy = w/1800, h/1013

BLOQUES = [
    ("00_titulo",  0,           int(685*sy), w,            int(740*sy)),
    ("01_temp",    0,           int(740*sy), int(175*sx),  int(870*sy)),
    ("02_tmax",    int(175*sx), int(740*sy), int(345*sx),  int(800*sy)),
    ("03_tmin",    int(175*sx), int(800*sy), int(345*sx),  int(870*sy)),
    ("04_humedad", int(345*sx), int(740*sy), int(560*sx),  int(870*sy)),
    ("05_presion", int(560*sx), int(740*sy), int(770*sx),  int(870*sy)),
    ("06_viento",  int(770*sx), int(740*sy), int(980*sx),  int(870*sy)),
    ("07_rafaga",  int(980*sx), int(740*sy), int(1190*sx), int(870*sy)),
    ("08_lluvia",  int(1190*sx),int(740*sy), int(1400*sx), int(870*sy)),
]

print("\nRecortando y procesando bloques...")
resultados_por_bloque = []

for nombre, x1, y1, x2, y2 in BLOQUES:
    if x2 <= x1 or y2 <= y1:
        continue

    bloque = img.crop((x1, y1, x2, y2))
    bloque_arr = np.array(bloque.convert("RGB"))

    # ── Estrategia: extraer píxeles blancos/claros (texto) ──────────────
    # El texto en Meteobridge es blanco o casi blanco
    # Umbral: píxeles donde R, G y B son todos > 180
    r_ch = bloque_arr[:,:,0].astype(int)
    g_ch = bloque_arr[:,:,1].astype(int)
    b_ch = bloque_arr[:,:,2].astype(int)

    # Máscara de texto blanco
    mascara_blanca = (r_ch > 180) & (g_ch > 180) & (b_ch > 180)

    # Crear imagen binaria: texto negro sobre fondo blanco
    binaria = np.ones_like(r_ch) * 255  # fondo blanco
    binaria[mascara_blanca] = 0          # texto negro

    img_bin = Image.fromarray(binaria.astype(np.uint8))

    # Escalar x4
    img_bin = img_bin.resize((img_bin.width*4, img_bin.height*4), Image.NEAREST)

    # Guardar bloque para inspección
    img_bin.save(f"dc_bloque_{nombre}.png")

    # OCR en este bloque
    texto = pytesseract.image_to_string(
        img_bin, lang="eng",
        config="--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789.-+CMINaxteHumPrisóVnRfgLuvjp%°/hkm "
    ).strip()

    print(f"  [{nombre}] → '{texto[:60]}'")
    resultados_por_bloque.append(f"=== {nombre} ===\n{texto}")

# ── También probar con la franja completa usando extracción de blancos ───────
print("\nProbando franja completa con extracción de blancos...")
top = int(h * 0.74)
franja = img.crop((0, top, w, h))
arr_f = np.array(franja.convert("RGB"))

r_f = arr_f[:,:,0].astype(int)
g_f = arr_f[:,:,1].astype(int)
b_f = arr_f[:,:,2].astype(int)

mascara = (r_f > 175) & (g_f > 175) & (b_f > 175)
binaria_f = np.ones_like(r_f) * 255
binaria_f[mascara] = 0

img_final = Image.fromarray(binaria_f.astype(np.uint8))
img_final = img_final.resize((img_final.width*2, img_final.height*2), Image.NEAREST)
img_final.save("dc_final.png")
print("Guardada: dc_final.png")

texto_final = pytesseract.image_to_string(
    img_final, lang="eng", config="--psm 6 --oem 3"
).strip()
print(f"\nTexto franja completa:\n{texto_final}")

# Guardar resultado
with open("dc_resultado.txt", "w", encoding="utf-8") as f:
    f.write("=== FRANJA COMPLETA ===\n")
    f.write(texto_final + "\n\n")
    f.write("\n".join(resultados_por_bloque))

print("\nGuardado: dc_resultado.txt")
print("\nInspeccionar dc_bloque_01_temp.png para ver si el texto es legible.")
