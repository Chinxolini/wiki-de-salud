"""
Generador de informes de laboratorio sintéticos en HTML — IMPACTLAB.

Toma un paciente de la cohorte (ver generar_cohorte.py) y produce un HTML
listo para imprimir a PDF (Ctrl+P → Guardar como PDF), imitando el formato
de un informe de laboratorio clínico chileno real.

Pieza clave para la demo: distintos "centros" nombran los mismos analitos de
forma distinta (VOCABULARIOS). Esto es lo que después se usa para demostrar
la normalización de datos clínicos heterogéneos.

Uso:
    python generar_ficha_pdf.py --paciente cohorte.json --index 0 --centro centro_a --out ficha.html
    python generar_ficha_pdf.py --paciente cohorte.json --index 0 --centro centro_b --out ficha_b.html

No usa PII real: el paciente se identifica solo por su seudónimo PAC-XXXX.
"""

import argparse
import json
import random
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# VOCABULARIOS — mismo analito, nombre distinto según el centro que emite el
# informe. Cada entrada: clave interna -> (nombre_mostrado, unidad, rango_ref)
# ---------------------------------------------------------------------------
VOCABULARIOS = {
    "centro_a": {
        "nombre_centro": "Centro Médico San Rafael",
        "direccion": "Av. Providencia 1234, Providencia, Santiago",
        "analitos": {
            "glicemia": ("Glicemia en ayunas", "mg/dL", "70 – 100"),
            "hemoglobina": ("Hemoglobina", "g/dL", "12.0 – 16.0"),
            "colesterol_total": ("Colesterol total", "mg/dL", "< 200"),
            "creatinina": ("Creatinina sérica", "mg/dL", "0.6 – 1.3"),
            "leucocitos": ("Recuento de leucocitos", "/mm³", "4.500 – 11.000"),
        },
    },
    "centro_b": {
        "nombre_centro": "Laboratorio Clínico Los Andes",
        "direccion": "Calle Los Alerces 567, Ñuñoa, Santiago",
        "analitos": {
            "glicemia": ("Glucosa basal", "mg/dL", "74 – 106"),
            "hemoglobina": ("Hb", "g/dL", "12.5 – 15.5"),
            "colesterol_total": ("Colesterol Total (CT)", "mg/dL", "hasta 199"),
            "creatinina": ("Creatininemia", "mg/dL", "0.5 – 1.2"),
            "leucocitos": ("Leucocitos totales", "cél/mm³", "4.000 – 10.500"),
        },
    },
    "centro_c": {
        "nombre_centro": "Red de Salud Cordillera",
        "direccion": "Av. Vicuña Mackenna 8900, La Florida, Santiago",
        "analitos": {
            "glicemia": ("GLUCOSA (ayuno)", "mg/dL", "70-99"),
            "hemoglobina": ("HGB", "g/dL", "13.0-17.0 (H) / 12.0-15.0 (M)"),
            "colesterol_total": ("COL-TOTAL", "mg/dL", "Deseable: <200"),
            "creatinina": ("CREA", "mg/dL", "0.7-1.4"),
            "leucocitos": ("WBC", "10^3/uL", "4.5-11.0"),
        },
    },
}

# Rangos de generación de valores plausibles por analito (unidades del §centro_a,
# se reescalan si el centro usa otra unidad — en este set las unidades son
# equivalentes salvo leucocitos, que se maneja aparte).
RANGOS_VALOR_PLAUSIBLE = {
    "glicemia": (65, 180),          # mg/dL — incluye normales y algunos alterados
    "hemoglobina": (10.5, 17.0),    # g/dL
    "colesterol_total": (140, 260), # mg/dL
    "creatinina": (0.5, 1.8),       # mg/dL
    "leucocitos": (3500, 13000),    # /mm3 (centro_c usa 10^3/uL, se convierte)
}


def generar_valores(rng: random.Random) -> dict:
    """Genera valores de laboratorio plausibles (no ligados a un paciente real)."""
    valores = {}
    for analito, (lo, hi) in RANGOS_VALOR_PLAUSIBLE.items():
        if isinstance(lo, int) and isinstance(hi, int):
            valores[analito] = rng.randint(lo, hi)
        else:
            valores[analito] = round(rng.uniform(lo, hi), 1)
    return valores


def formatear_valor(analito: str, valor, centro: str):
    """Ajusta la representación del valor según la unidad usada por el centro."""
    if analito == "leucocitos" and centro == "centro_c":
        # centro_c reporta en 10^3/uL en vez de /mm3 (numéricamente equivalente
        # /1000, ya que 1 /mm3 == 1 cél/uL)
        return round(valor / 1000, 1)
    return valor


def render_ficha(paciente: dict, centro: str = "centro_a", seed: int = None) -> str:
    """
    Genera el HTML del informe de laboratorio para `paciente`, con la
    nomenclatura de analitos propia de `centro`. Devuelve el HTML como string.

    `seed`: si se pasa, fija la semilla para valores reproducibles; si no,
    se deriva del paciente_ref para que sea reproducible por paciente.
    """
    if centro not in VOCABULARIOS:
        raise ValueError(f"Centro desconocido: {centro}. Opciones: {list(VOCABULARIOS.keys())}")

    if seed is None:
        seed = hash(paciente["paciente_ref"]) & 0xFFFFFFFF
    rng = random.Random(seed)

    vocab = VOCABULARIOS[centro]
    valores = generar_valores(rng)
    fecha_informe = date.today().isoformat()

    filas_html = ""
    for analito, (nombre, unidad, rango) in vocab["analitos"].items():
        valor = formatear_valor(analito, valores[analito], centro)
        filas_html += f"""
        <tr>
            <td>{nombre}</td>
            <td style="text-align:center">{valor}</td>
            <td style="text-align:center">{unidad}</td>
            <td style="text-align:center">{rango}</td>
        </tr>"""

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe de Laboratorio — {paciente['paciente_ref']}</title>
<style>
    body {{
        font-family: Arial, Helvetica, sans-serif;
        font-size: 13px;
        color: #1a1a1a;
        max-width: 720px;
        margin: 20px auto;
        padding: 0 16px;
    }}
    .encabezado {{
        border-bottom: 2px solid #2c3e50;
        padding-bottom: 10px;
        margin-bottom: 16px;
    }}
    .encabezado h1 {{
        font-size: 18px;
        margin: 0 0 2px 0;
        color: #2c3e50;
    }}
    .encabezado p {{
        margin: 0;
        font-size: 11px;
        color: #555;
    }}
    .datos-paciente {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 4px 20px;
        margin-bottom: 18px;
        background: #f5f6f7;
        padding: 10px 14px;
        border-radius: 4px;
    }}
    .datos-paciente div {{
        font-size: 12px;
    }}
    .datos-paciente strong {{
        color: #2c3e50;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 6px;
    }}
    th, td {{
        border: 1px solid #d0d4d8;
        padding: 6px 8px;
        font-size: 12px;
    }}
    th {{
        background: #2c3e50;
        color: white;
        text-align: left;
    }}
    .pie {{
        margin-top: 24px;
        font-size: 10px;
        color: #888;
        border-top: 1px solid #d0d4d8;
        padding-top: 8px;
    }}
    .sintetico {{
        margin-top: 4px;
        font-size: 10px;
        color: #b03030;
        font-weight: bold;
    }}
</style>
</head>
<body>

<div class="encabezado">
    <h1>{vocab['nombre_centro']}</h1>
    <p>{vocab['direccion']}</p>
    <p>INFORME DE LABORATORIO CLÍNICO</p>
</div>

<div class="datos-paciente">
    <div><strong>Paciente (ref.):</strong> {paciente['paciente_ref']}</div>
    <div><strong>Fecha de informe:</strong> {fecha_informe}</div>
    <div><strong>Sexo:</strong> {paciente.get('sexo', '—')}</div>
    <div><strong>Edad:</strong> {paciente.get('edad', '—')} años</div>
    <div><strong>Tramo FONASA:</strong> {paciente.get('tramo_fonasa', '—')}</div>
    <div><strong>Servicio de Salud:</strong> {paciente.get('servicio_salud', '—')}</div>
</div>

<table>
    <thead>
        <tr>
            <th>Analito</th>
            <th style="text-align:center">Valor</th>
            <th style="text-align:center">Unidad</th>
            <th style="text-align:center">Rango de referencia</th>
        </tr>
    </thead>
    <tbody>{filas_html}
    </tbody>
</table>

<div class="pie">
    Informe generado electrónicamente. Los valores no requieren firma manuscrita.
</div>
<div class="sintetico">
    DATO SINTÉTICO — generado por IMPACTLAB con fines de demostración. No corresponde a un paciente real.
</div>

</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(
        description="Genera un informe de laboratorio HTML sintético para un paciente de la cohorte."
    )
    parser.add_argument("--paciente", type=str, required=True, help="Archivo JSON de cohorte (ver generar_cohorte.py)")
    parser.add_argument("--index", type=int, default=0, help="Índice del paciente dentro de la cohorte (default: 0)")
    parser.add_argument("--centro", type=str, default="centro_a", choices=list(VOCABULARIOS.keys()), help="Centro emisor (define vocabulario)")
    parser.add_argument("--out", type=str, default="ficha.html", help="Archivo HTML de salida (default: ficha.html)")
    args = parser.parse_args()

    with open(args.paciente, "r", encoding="utf-8") as f:
        cohorte = json.load(f)

    if args.index >= len(cohorte):
        raise SystemExit(f"Índice {args.index} fuera de rango: la cohorte tiene {len(cohorte)} pacientes.")

    paciente = cohorte[args.index]
    html = render_ficha(paciente, centro=args.centro)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Ficha generada: {paciente['paciente_ref']} ({args.centro}) → {args.out}")


if __name__ == "__main__":
    main()
