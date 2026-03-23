"""
test_ocr_dc.py
==============
Diagnóstico y calibración del OCR para la EMA Defensa Civil.
Descarga la imagen, recorta la franja de datos y testea el OCR.

Corré este script primero para calibrar, luego usamos dc_saladillo.py.

Dependencias:
    pip install pytesseract pillow requests
    + Tesseract instalado en C:\\Program Files\\Tesseract-OCR\\
"""

import requests
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re

# Ruta de Tesseract en Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

URL_CAM = "https://content.meteobridge.com/cam/791751a5ea5fe89561a11d743920c3ef/camplus.jpg"

def descargar_imagen():
    r = requests.get(URL_CAM, timeout=15)
    r.raise_for_status()
    return Image.open(BytesIO(r.content))

def probar_recortes(img):
    w, h = img.size
    print(f"Imagen original: {w}x{h}")

    # Probamos 4 recortes distintos de la franja inferior
    recortes = {
        "franja_10pct":  img.crop((0, int(h*0.88), w, h)),
        "franja_15pct":  img.crop((0, int(h*0.82), w, h)),
        "franja_20pct":  img.crop((0, int(h*0.75), w, h)),
        "mitad_inferior": img.crop((0, h//2, w, h)),
    }

    for nombre, recorte in recortes.items():
        recorte.save(f"recorte_{nombre}.jpg")
        print(f"\n── {nombre} ({recorte.size}) ──")

        # OCR directo
        texto = pytesseract.image_to_string(recorte, lang="eng",
            config="--psm 6 --oem 3")
        print("OCR directo:")
        print(texto[:300])

        # OCR con preprocesamiento
        gris = recorte.convert("L")
        gris = ImageEnhance.Contrast(gris).enhance(2.5)
        gris = gris.filter(ImageFilter.SHARPEN)
        texto2 = pytesseract.image_to_string(gris, lang="eng",
            config="--psm 6 --oem 3")
        print("OCR preprocesado:")
        print(texto2[:300])

def extraer_valores_test(img):
    """Intenta extraer los valores clave de la franja inferior."""
    w, h = img.size
    franja = img.crop((0, int(h*0.85), w, h))

    # Preprocesar: escala de grises + contraste + escalar x2
    gris = franja.convert("L")
    gris = gris.resize((gris.width*2, gris.height*2), Image.LANCZOS)
    gris = ImageEnhance.Contrast(gris).enhance(3.0)
    gris = ImageEnhance.Sharpness(gris).enhance(2.0)
    gris.save("franja_procesada.jpg")

    texto = pytesseract.image_to_string(gris, lang="eng",
        config="--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789.,°%ChmkWNSEOr/ ():")

    print("\n══ TEXTO EXTRAÍDO DE FRANJA PROCESADA ══")
    print(texto)
    print("════════════════════════════════════════")

    # Buscar patrones de valores meteorológicos
    patrones = {
        "Temperatura": r"(\d+\.?\d*)\s*[°o]?\s*C",
        "Humedad":     r"(\d+)\s*%",
        "Presion":     r"(\d{3,4}\.?\d*)\s*hPa",
        "Viento":      r"(\d+\.?\d*)\s*km[\/\s]?h",
        "Lluvia":      r"(\d+\.?\d*)\s*mm",
    }
    print("\n── Valores encontrados por patrón ──")
    for nombre, patron in patrones.items():
        m = re.search(patron, texto, re.IGNORECASE)
        print(f"  {nombre:<15}: {m.group(0) if m else 'no encontrado'}")

if __name__ == "__main__":
    print("Descargando imagen...")
    img = descargar_imagen()
    print("OK\n")

    print("=== TEST DE RECORTES ===")
    probar_recortes(img)

    print("\n=== EXTRACCIÓN DE VALORES ===")
    extraer_valores_test(img)

    print("\nArchivos guardados:")
    print("  recorte_franja_10pct.jpg")
    print("  recorte_franja_15pct.jpg")
    print("  recorte_franja_20pct.jpg")
    print("  franja_procesada.jpg")
    print("\nAbrí esos archivos para ver qué recorte captura mejor los datos.")
