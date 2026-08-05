"""Genera fichas clínicas sintéticas COMPLETAS — L3 ampliado.

Antes solo emitíamos informes de laboratorio, y eso dejaba fuera lo que de
verdad hace difícil reunir un historial: los diagnósticos que cada centro
escribe distinto, los medicamentos por nombre comercial en un lado y por
principio activo en otro, las alergias que aparecen en un solo documento, y los
motivos de consulta escritos en prosa.

Los tres centros describen a la MISMA persona y se contradicen en la forma, no
en el fondo. Ahí está el valor del producto:

  - "DM2" / "Diabetes Mellitus tipo 2" / "diabetes tipo II"
  - "Losartán 50mg" / "COZAAR 50 mg" / "losartan potasico 50"
  - leucocitos en /mm³ contra 10³/µL
  - la alergia a penicilina consta en un centro y en los otros dos no

Uso:
    python generador/generar_ficha_completa.py
    python generador/generar_ficha_completa.py --salida ../demo
"""

import argparse
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parent / "demo"

BASE_CSS = """
  body{font-family:{FUENTE};font-size:13px;color:#1a1a1a;max-width:760px;margin:20px auto;padding:0 18px}
  .cab{border-bottom:3px solid {COLOR};padding-bottom:10px;margin-bottom:16px}
  .cab h1{font-size:17px;margin:0 0 3px;color:{COLOR}}
  .cab p{margin:0;font-size:11px;color:#555}
  .datos{display:grid;grid-template-columns:1fr 1fr;gap:4px 20px;margin-bottom:18px;
    background:#f5f6f7;padding:11px 14px;border-radius:4px;font-size:12px}
  h2{font-size:13px;color:{COLOR};border-bottom:1px solid #d0d4d8;padding-bottom:4px;
    margin:22px 0 8px;text-transform:uppercase;letter-spacing:.04em}
  table{width:100%;border-collapse:collapse;margin-top:6px}
  th,td{border:1px solid #d0d4d8;padding:5px 8px;font-size:12px;vertical-align:top}
  th{background:{COLOR};color:#fff;text-align:left}
  ul{margin:6px 0;padding-left:20px;font-size:12px}
  li{margin-bottom:3px}
  .prosa{font-size:12px;line-height:1.55;margin:6px 0}
  .pie{margin-top:26px;font-size:10px;color:#888;border-top:1px solid #d0d4d8;padding-top:8px}
  .sint{margin-top:4px;font-size:10px;color:#b03030;font-weight:bold}
"""


def envoltura(titulo, color, fuente, cabecera, cuerpo):
    css = BASE_CSS.replace("{COLOR}", color).replace("{FUENTE}", fuente)
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{titulo}</title>
<style>{css}</style>
</head>
<body>
{cabecera}
{cuerpo}
<div class="pie">Documento generado electrónicamente. Los valores no requieren firma manuscrita.</div>
<div class="sint">DATO SINTÉTICO — generado por IMPACTLAB con fines de demostración.
No corresponde a un paciente real.</div>
</body>
</html>
"""


# ---------------------------------------------------------------- CENTRO A
# Privado, formato tabular limpio. Usa siglas y nombres comerciales.
def centro_a():
    cabecera = """
<div class="cab">
  <h1>Centro Médico San Rafael</h1>
  <p>Av. Providencia 1234, Providencia, Santiago</p>
  <p>RESUMEN DE FICHA CLÍNICA — Solicitud Art. 13 Ley 20.584</p>
</div>
<div class="datos">
  <div><b>Paciente (ref.):</b> PAC-0006</div>
  <div><b>Emisión:</b> 2026-08-05</div>
  <div><b>Sexo:</b> M</div>
  <div><b>Edad:</b> 76 años</div>
  <div><b>Previsión:</b> FONASA C</div>
  <div><b>Ficha N°:</b> SR-118342</div>
</div>"""

    cuerpo = """
<h2>Antecedentes mórbidos</h2>
<table>
  <tr><th>Fecha dg.</th><th>Diagnóstico</th><th>Estado</th></tr>
  <tr><td>2014-03</td><td>DM2</td><td>Activo</td></tr>
  <tr><td>2016-11</td><td>HTA esencial</td><td>Activo</td></tr>
  <tr><td>2019-07</td><td>Dislipidemia mixta</td><td>Activo</td></tr>
  <tr><td>2021-02</td><td>Artrosis rodilla derecha</td><td>Activo</td></tr>
</table>

<h2>Alergias</h2>
<ul>
  <li><b>Penicilina</b> — exantema generalizado. Reacción moderada, consignada 2009.</li>
  <li>AINEs: no refiere.</li>
</ul>

<h2>Fármacos en uso</h2>
<table>
  <tr><th>Producto</th><th>Dosis</th><th>Posología</th></tr>
  <tr><td>METFORMINA LCH 850 mg</td><td>850 mg</td><td>1 comp. c/12 h</td></tr>
  <tr><td>COZAAR 50 mg</td><td>50 mg</td><td>1 comp. al día</td></tr>
  <tr><td>Atorvastatina 20 mg</td><td>20 mg</td><td>1 comp. en la noche</td></tr>
</table>

<h2>Laboratorio — 2026-07-28</h2>
<table>
  <tr><th>Analito</th><th>Valor</th><th>Unidad</th><th>Referencia</th></tr>
  <tr><td>Glicemia en ayunas</td><td>132</td><td>mg/dL</td><td>70 – 100</td></tr>
  <tr><td>Hemoglobina glicosilada</td><td>7.4</td><td>%</td><td>&lt; 5.7</td></tr>
  <tr><td>Hemoglobina</td><td>13.1</td><td>g/dL</td><td>12.0 – 16.0</td></tr>
  <tr><td>Colesterol total</td><td>177</td><td>mg/dL</td><td>&lt; 200</td></tr>
  <tr><td>Creatinina sérica</td><td>1.1</td><td>mg/dL</td><td>0.6 – 1.3</td></tr>
  <tr><td>Recuento de leucocitos</td><td>7705</td><td>/mm³</td><td>4.500 – 11.000</td></tr>
</table>

<h2>Atenciones registradas</h2>
<table>
  <tr><th>Fecha</th><th>Especialidad</th><th>Motivo</th></tr>
  <tr><td>2026-07-28</td><td>Medicina Interna</td><td>Control DM2 e HTA. Refiere buena adherencia.</td></tr>
  <tr><td>2025-12-03</td><td>Traumatología</td><td>Gonalgia derecha de 6 meses, aumenta al subir escaleras.</td></tr>
</table>"""
    return envoltura("Ficha Clínica — Centro Médico San Rafael",
                     "#2c3e50", "Arial, Helvetica, sans-serif", cabecera, cuerpo)


# ---------------------------------------------------------------- CENTRO B
# Publico. Epicrisis en prosa, nombres completos, otra unidad para leucocitos.
def centro_b():
    cabecera = """
<div class="cab">
  <h1>Hospital Regional de Ñuble</h1>
  <p>Servicio de Salud Ñuble · Unidad de Gestión de Fichas Clínicas</p>
  <p>EPICRISIS Y RESUMEN DE HOSPITALIZACIÓN</p>
</div>
<div class="datos">
  <div><b>Paciente (ref.):</b> PAC-0006</div>
  <div><b>N° Ingreso:</b> 2024-44127</div>
  <div><b>Ingreso:</b> 12-09-2024</div>
  <div><b>Alta:</b> 18-09-2024</div>
  <div><b>Servicio:</b> Cirugía General</div>
  <div><b>Previsión:</b> FONASA C</div>
</div>"""

    cuerpo = """
<h2>Motivo de ingreso</h2>
<p class="prosa">Paciente de 74 años consulta en Servicio de Urgencia por cuadro de 18 horas de
evolución caracterizado por <b>dolor abdominal en hipocondrio derecho</b>, de carácter cólico,
irradiado a dorso, asociado a náuseas y dos episodios de vómitos. Refiere episodios similares
autolimitados en los últimos 8 meses, sin consulta previa.</p>

<h2>Antecedentes consignados al ingreso</h2>
<ul>
  <li>Diabetes Mellitus tipo 2, en tratamiento desde 2014.</li>
  <li>Hipertensión arterial esencial.</li>
  <li>Alergia a Penicilina (exantema). <b>Consignada en brazalete de riesgo.</b></li>
</ul>

<h2>Intervención</h2>
<p class="prosa">Se realiza <b>colecistectomía laparoscópica</b> el 13-09-2024 sin incidentes.
Hallazgo intraoperatorio: vesícula de paredes engrosadas con múltiples cálculos.
Cirujano responsable: equipo de turno.</p>

<h2>Exámenes durante la hospitalización</h2>
<table>
  <tr><th>Examen</th><th>Resultado</th><th>Unidad</th><th>Fecha</th></tr>
  <tr><td>Leucocitos</td><td>14.2</td><td>10³/µL</td><td>12-09-2024</td></tr>
  <tr><td>Proteína C reactiva</td><td>86</td><td>mg/L</td><td>12-09-2024</td></tr>
  <tr><td>Glucosa plasmática en ayuno</td><td>148</td><td>mg/dL</td><td>13-09-2024</td></tr>
  <tr><td>Creatinina</td><td>1.0</td><td>mg/dL</td><td>13-09-2024</td></tr>
</table>

<h2>Imagenología</h2>
<p class="prosa"><b>Ecotomografía abdominal (12-09-2024).</b> Conclusión del informe:
"Vesícula biliar de paredes engrosadas de 5 mm, con múltiples imágenes litiásicas en su interior,
la mayor de 12 mm. Vía biliar de calibre conservado. Hígado, páncreas y riñones sin hallazgos."</p>

<h2>Indicaciones al alta</h2>
<ul>
  <li>Continuar Metformina 850 mg cada 12 horas.</li>
  <li>Losartán potásico 50 mg al día.</li>
  <li>Control en policlínico de cirugía en 14 días.</li>
</ul>"""
    return envoltura("Epicrisis — Hospital Regional de Ñuble",
                     "#1b4f72", "Georgia, 'Times New Roman', serif", cabecera, cuerpo)


# ---------------------------------------------------------------- CENTRO C
# Ambulatorio. Todo en prosa corrida, sin tablas, con abreviaturas informales.
def centro_c():
    cabecera = """
<div class="cab">
  <h1>Red de Salud Cordillera</h1>
  <p>Centro Ambulatorio · Registro de atenciones</p>
  <p>COPIA DE REGISTRO CLÍNICO AMBULATORIO</p>
</div>
<div class="datos">
  <div><b>Paciente (ref.):</b> PAC-0006</div>
  <div><b>Emisión:</b> 04-08-2026</div>
  <div><b>Rango solicitado:</b> 2022 – 2026</div>
  <div><b>Registros:</b> 4 atenciones</div>
</div>"""

    cuerpo = """
<h2>Atenciones</h2>

<p class="prosa"><b>15-04-2026 · Kinesiología.</b> Ingresa a programa por gonalgia der. Refiere
dolor 6/10 EVA al subir escaleras y al levantarse tras estar sentado. Se indica pauta de
fortalecimiento de cuádriceps, 10 sesiones.</p>

<p class="prosa"><b>22-01-2026 · Medicina General.</b> Consulta por <b>lumbago mecánico</b> de 3
semanas. Sin irradiación ni déficit neurológico. Se solicita radiografía. Indicación: paracetamol
1 g c/8 h por 5 días y reposo relativo.</p>

<p class="prosa"><b>22-01-2026 · Imagenología.</b> Rx columna lumbosacra AP y lateral. Informe:
"Signos de espondiloartrosis lumbar de predominio L4-L5. Disminución del espacio intervertebral
L4-L5. Alineación conservada. No se observan lesiones líticas ni blásticas."</p>

<p class="prosa"><b>09-08-2022 · Oftalmología.</b> Control anual por diabetes tipo II. Fondo de ojo:
sin signos de retinopatía diabética en ambos ojos. Se indica control anual.</p>

<h2>Fármacos registrados en este centro</h2>
<p class="prosa">losartan potasico 50 — 1 al dia. metformina 850 — 1 cada 12 hrs.
paracetamol 1 g SOS dolor (indicado 01-2026, uso puntual).</p>

<h2>Observaciones</h2>
<p class="prosa">Paciente refiere alergia a antibióticos, no recuerda cuál. Se registra como
alergia no precisada, pendiente de confirmar con otro prestador.</p>

<h2>Laboratorio 2026</h2>
<p class="prosa">Perfil lipídico 10-03-2026: colesterol total 184 mg/dl, HDL 41 mg/dl,
LDL 112 mg/dl, triglicéridos 155 mg/dl. Hemoglobina glicada 7.1%.</p>"""
    return envoltura("Registro Ambulatorio — Red de Salud Cordillera",
                     "#5b3a29", "Verdana, Geneva, sans-serif", cabecera, cuerpo)


CENTROS = {
    "ficha-centro_a.html": centro_a,
    "ficha-centro_b.html": centro_b,
    "ficha-centro_c.html": centro_c,
}


def main():
    ap = argparse.ArgumentParser(description="Genera las fichas clínicas sintéticas completas")
    ap.add_argument("--salida", default=str(SALIDA))
    args = ap.parse_args()

    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, fn in CENTROS.items():
        (destino / nombre).write_text(fn(), encoding="utf-8")
        print(f"  {destino / nombre}")
    print(f"\n{len(CENTROS)} fichas completas. La misma persona, tres formatos que no se hablan.")


if __name__ == "__main__":
    main()
