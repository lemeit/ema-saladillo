import requests, json, warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

r = requests.post(
    'https://snih.hidricosargentina.gob.ar/MuestraDatos.aspx/LeerUltimosRegistros',
    headers={'Content-Type': 'application/json; charset=utf-8', 'X-Requested-With': 'XMLHttpRequest'},
    data=json.dumps({'fechaDesde': '2026-03-20', 'fechaHasta': '2026-03-21', 'estacion': '284094', 'codigo': '14'}),
    verify=False, timeout=15
)

datos = r.json()['d']['Mediciones']
print(f"Total registros: {len(datos)}\n")
for m in datos[:15]:
    for med in m['Mediciones']:
        if med['Codigo'] == 14:
            print(m['FechaHora'], '->', med['Valor'], '°C')
