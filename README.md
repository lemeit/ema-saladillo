# Red EMA Saladillo

Sistema de adquisición y visualización de datos meteorológicos de 4 estaciones automáticas en Saladillo, Buenos Aires, Argentina.

## Estaciones

| Código | Nombre | Método | Coordenadas |
|--------|--------|--------|-------------|
| **EMA-EET** | EEST N°1 "Gral. Savio" | API SNIH/INA | -35.64533, -59.78482 |
| **EMA-CFR** | Centro de Formación Rural | HTML scraping | -35.60063, -59.81350 |
| **EMA-DC** | Defensa Civil — Aeródromo | OCR imagen Meteobridge | -35.60000, -59.80000 |
| **EMA-CS** | Clima Saladillo — B° Falucho | JSON Meteotemplate | -35.64500, -59.77580 |

## Arquitectura

```
Scrapers (GitHub Actions, cada 1h)
    ↓
Supabase (PostgreSQL)
    ↓
Dashboard HTML estático (Netlify)
```

## Scrapers

| Script | Estación | Descripción |
|--------|----------|-------------|
| `scrapers/snih_saladillo_v3.py` | EMA-EET | API POST JSON al SNIH/INA |
| `scrapers/cfr_saladillo.py` | EMA-CFR | Scraping HTML con BeautifulSoup |
| `scrapers/dc_saladillo.py` | EMA-DC | OCR con Tesseract sobre imagen JPG |
| `scrapers/cs_saladillo.py` | EMA-CS | Endpoint JSON de Meteotemplate |
| `scrapers/supabase_ping.py` | — | Ping diario para evitar pausa de Supabase |

## Instalación local

```bash
pip install -r requirements.txt
# + Tesseract OCR instalado en el sistema (solo para EMA-DC)
```

## Variables de entorno (GitHub Actions / GitLab CI)

Los scripts usan credenciales de Supabase hardcodeadas para facilitar el uso educativo local. Para producción en CI, se recomienda migrar a secrets:

```
SUPA_URL=https://xxxx.supabase.co
SUPA_KEY=eyJ...
```

## Dashboard

El archivo `dashboard/index.html` es un single-file HTML estático que lee directamente de Supabase via REST API. No requiere backend. Deployable en Netlify, GitHub Pages o cualquier hosting estático.

## Base de datos (Supabase)

Tablas: `mediciones_ema`, `mediciones_cfr`, `mediciones_dc`, `mediciones_cs`

Vistas: `v_ema_armonizada`, `v_temperatura_comparativa`

## Proyecto educativo

Laboratorio de Industrias · 7° Año Técnico Químico  
EEST N°1 "Gral. Savio" · Saladillo · Buenos Aires · 2026  
Ing. Luciano Lamaita

## Licencia

Datos meteorológicos: Creative Commons (EMA-EET/SNIH), uso público (EMA-CFR, EMA-DC, EMA-CS).  
Código: MIT.
