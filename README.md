# Red EMA Saladillo

Sistema de adquisición y visualización de datos meteorológicos de 4 estaciones automáticas en Saladillo, Buenos Aires, Argentina. Publicado en [emas.lemeit.ar](https://emas.lemeit.ar).

Es uno de tres proyectos de monitoreo ambiental que comparten la misma infraestructura de Cloudflare (Pages + Workers + D1), pensados para integrarse a futuro: este (meteorología), [aq.lemeit.ar](https://aq.lemeit.ar) (calidad del aire, sensores PurpleAir) y wq.lemeit.ar (calidad del agua, en desarrollo).

## Estaciones

| Código | Nombre | Método | Coordenadas |
|--------|--------|--------|-------------|
| **EMA-EET** | EEST N°1 "Gral. Savio" | API SNIH/INA | -35.64533, -59.78482 |
| **EMA-CFR** | Centro de Formación Rural | HTML scraping | -35.62236, -59.78359 |
| **EMA-DC** | Defensa Civil — Aeródromo | OCR imagen Meteobridge | -35.60063, -59.81350 |
| **EMA-CS** | Clima Saladillo — B° Falucho | JSON Meteotemplate | -35.64500, -59.77580 |

## Arquitectura

```
Scrapers (GitHub Actions, cron horario)
    ↓ (Cloudflare D1 HTTP API)
Cloudflare D1 — tabla unificada "mediciones"
    ↓ (consultada por)
Worker "ema-saladillo-api" (Cloudflare Workers)
    ↓ (mismo formato de consulta que antes usaba PostgREST/Supabase)
Dashboard HTML estático (Cloudflare Pages) — emas.lemeit.ar
```

Hasta agosto de 2026 la base de datos era Supabase (PostgreSQL), con 4 tablas separadas (una por estación). Se migró todo el historial (~30.200 filas) a una tabla D1 unificada, y se agregó el Worker como capa de compatibilidad para no tener que reescribir el dashboard. Ver `worker/` y `d1/schema.sql`.

## Scrapers

| Script | Estación | Descripción |
|--------|----------|-------------|
| `scrapers/snih_saladillo_v3.py` | EMA-EET | API POST JSON al SNIH/INA |
| `scrapers/cfr_saladillo.py` | EMA-CFR | Scraping HTML con BeautifulSoup |
| `scrapers/dc_saladillo.py` | EMA-DC | OCR con Tesseract sobre imagen JPG |
| `scrapers/cs_saladillo.py` | EMA-CS | Endpoint JSON de Meteotemplate |
| `scrapers/d1_writer.py` | — | Helper compartido: escribe en D1 vía la API HTTP de Cloudflare |
| `scrapers/supabase_ping.py` | — | Ping diario a Supabase (proyecto compartido con otras apps personales, no relacionado a EMA) |

## Instalación local

```bash
pip install -r requirements.txt
# + Tesseract OCR instalado en el sistema (solo para EMA-DC)
```

## Variables de entorno (GitHub Actions)

Los 4 scrapers escriben en D1 a través de la API HTTP de Cloudflare (`scrapers/d1_writer.py`). Se configuran como secrets del repositorio:

```
CF_ACCOUNT_ID=...
CF_DATABASE_ID=b5b1eef7-5c8d-42a8-a23e-69cd5ae1cd30
CF_API_TOKEN=...   # con permiso D1:Edit
```

`supabase_ping.py` sigue usando `SUPA_URL` / `SUPA_KEY` por separado — no tiene relación con EMA, solo mantiene activo el proyecto Supabase compartido con otras apps.

## Dashboard

El archivo `index.html` (raíz del repo) es un single-file HTML estático que consulta el Worker de Cloudflare vía REST. No requiere backend propio. Deployado en Cloudflare Pages (`wrangler pages deploy`).

## Base de datos (Cloudflare D1)

Base: `ema-saladillo-db` — tabla unificada `mediciones` (columna `estacion` distingue EMA-EET/CFR/DC/CS). Ver `d1/schema.sql` para el esquema completo, incluyendo el índice único que evita filas duplicadas.

El Worker `worker/src/index.js` expone rutas compatibles con el formato PostgREST que usaba el dashboard (`mediciones_ema`, `mediciones_cfr`, `mediciones_dc`, `mediciones_cs`, `v_ema_armonizada`, `v_temperatura_comparativa`), calculadas sobre la tabla unificada.

## Proyecto educativo

Laboratorio de Industrias · 7° Año Técnico Químico  
EEST N°1 "Gral. Savio" · Saladillo · Buenos Aires · 2026  
Ing. Luciano Lamaita — más proyectos y materiales en [profe.lemeit.ar](https://profe.lemeit.ar)

## Licencia

Datos meteorológicos: Creative Commons (EMA-EET/SNIH), uso público (EMA-CFR, EMA-DC, EMA-CS).  
Código: MIT.
