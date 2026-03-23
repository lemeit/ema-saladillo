import requests
url = "https://content.meteobridge.com/cam/791751a5ea5fe89561a11d743920c3ef/camplus.jpg"
r = requests.get(url, timeout=10)
print(f"HTTP {r.status_code} — {len(r.content)} bytes — {r.headers.get('content-type')}")
with open("cam_dc.jpg", "wb") as f:
    f.write(r.content)
print("Imagen guardada como cam_dc.jpg")