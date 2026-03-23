import requests
from PIL import Image
from io import BytesIO

url = "https://content.meteobridge.com/cam/791751a5ea5fe89561a11d743920c3ef/camplus.jpg"
r = requests.get(url, timeout=10)
img = Image.open(BytesIO(r.content))
print(f"Tamaño: {img.size}")  # (ancho, alto)
print(f"Modo: {img.mode}")

# Guardar para inspeccionar visualmente
img.save("cam_dc_actual.jpg")
print("Guardada como cam_dc_actual.jpg")