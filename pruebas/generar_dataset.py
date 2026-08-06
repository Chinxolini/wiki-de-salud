"""Generador de dataset de testing con verdad de referencia — IMPACTLAB.

Por qué existe. `generador/` produce fichas sintéticas y `extraccion/` las lee
con Claude, pero no había forma de medir si la extracción acertó: no existía
un "esto es lo que debería haber salido". Este script cierra ese hueco.

Qué genera. Para cada caso sintético:
  - 2 o 3 fichas HTML (una por centro), reutilizando los vocabularios de
    analitos ya definidos en `generador/generar_ficha_pdf.py` (VOCABULARIOS)
    y el envoltorio HTML de `generador/generar_ficha_completa.py` (envoltura).
    No se reinventan nombres de analito ni estilos: se importan.
  - un `verdad.json` con la extracción perfecta esperada según
    `schemas/wiki-salud.schema.json`: un registro completo por documento, más
    un resumen `canonico_esperado` de cómo deberían converger los centros.

Casos difíciles incluidos a propósito, en todos los casos generados:
  - conversión de unidades: leucocitos en /mm³ (centro_a), cél/mm³ (centro_b)
    y 10³/µL (centro_c) — mismo valor real, tres unidades.
  - nombre comercial vs. principio activo: "COZAAR 50 mg" (centro_a) vs.
    "Losartán potásico 50 mg" (centro_b) vs. "losartan potasico 50" (centro_c).
  - el mismo analito con nombre distinto en cada centro (ya viene de
    VOCABULARIOS: "Glicemia en ayunas" / "Glucosa basal" / "GLUCOSA (ayuno)").
  - al menos un caso con un valor ilegible en un centro, para probar
    `campos_ilegibles`.

Uso:
    python pruebas/generar_dataset.py --seed 42 --n 6
    python pruebas/generar_dataset.py --seed 42 --n 6 --out pruebas/dataset

Sin dependencias externas: solo stdlib. Todo dato es sintético (PAC-XXXX).
"""

import argparse
import json
import random
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))

# --- Legos reutilizados, NO reimplementados ---------------------------------
from generador.generar_ficha_completa import BASE_CSS, envoltura  # noqa: E402
from generador.generar_ficha_pdf import (  # noqa: E402
    VOCABULARIOS as ANALITO_VOCAB,
    generar_valores,
    formatear_valor,
)

SALIDA_DEFAULT = AQUI / "dataset"

# ---------------------------------------------------------------------------
# Unidad y nombre canónico por analito (el contrato al que toda extracción
# perfecta debe converger, sea cual sea el centro de origen).
# ---------------------------------------------------------------------------
ANALITOS_CANONICOS = {
    "glicemia": {"nombre_canonico": "Glicemia en ayunas", "unidad_canonica": "mg/dL", "rango": (70, 100)},
    "hemoglobina": {"nombre_canonico": "Hemoglobina", "unidad_canonica": "g/dL", "rango": (12.0, 16.0)},
    "colesterol_total": {"nombre_canonico": "Colesterol total", "unidad_canonica": "mg/dL", "rango": (0, 200)},
    "creatinina": {"nombre_canonico": "Creatinina sérica", "unidad_canonica": "mg/dL", "rango": (0.6, 1.3)},
    "leucocitos": {"nombre_canonico": "Recuento de leucocitos", "unidad_canonica": "10³/µL", "rango": (4.5, 11.0)},
}

# Analito que se usa como "campo ilegible" cuando el caso lo requiere.
ANALITO_ILEGIBLE = "creatinina"

# ---------------------------------------------------------------------------
# Diagnósticos: mismo dato, tres formas de escribirlo. No existe en generador/
# un vocabulario de diagnósticos reutilizable, así que se define acá.
# ---------------------------------------------------------------------------
DIAGNOSTICOS = {
    "dm2": {
        "canonico": "Diabetes Mellitus tipo 2",
        "estado": "activo",
        "por_centro": {
            "centro_a": "DM2",
            "centro_b": "Diabetes Mellitus tipo 2",
            "centro_c": "diabetes tipo II",
        },
    },
    "hta": {
        "canonico": "Hipertensión arterial esencial",
        "estado": "activo",
        "por_centro": {
            "centro_a": "HTA esencial",
            "centro_b": "Hipertensión arterial esencial",
            "centro_c": "HTA",
        },
    },
}

# ---------------------------------------------------------------------------
# Medicamentos: nombre comercial en un centro, principio activo en otro,
# escritura informal en el tercero. El caso "difícil" central del dataset.
# ---------------------------------------------------------------------------
MEDICAMENTOS = {
    "losartan": {
        "principio_activo": "Losartán potásico",
        "por_centro": {
            "centro_a": {"nombre": "COZAAR 50 mg", "dosis": "50 mg", "frecuencia": "1 comp. al día"},
            "centro_b": {"nombre": "Losartán potásico 50 mg", "dosis": "50 mg", "frecuencia": "al día"},
            "centro_c": {"nombre": "losartan potasico 50", "dosis": "50 mg", "frecuencia": "1 al día"},
        },
    },
    "metformina": {
        "principio_activo": "Metformina",
        "por_centro": {
            "centro_a": {"nombre": "METFORMINA LCH 850 mg", "dosis": "850 mg", "frecuencia": "1 comp. c/12 h"},
            "centro_b": {"nombre": "Metformina 850 mg", "dosis": "850 mg", "frecuencia": "cada 12 horas"},
            "centro_c": {"nombre": "metformina 850", "dosis": "850 mg", "frecuencia": "1 cada 12 hrs"},
        },
    },
}

CENTROS_ESTILO = {
    "centro_a": {"color": "#2c3e50", "fuente": "Arial, Helvetica, sans-serif", "titulo": "RESUMEN DE FICHA CLÍNICA — Solicitud Art. 13 Ley 20.584"},
    "centro_b": {"color": "#1b4f72", "fuente": "Georgia, 'Times New Roman', serif", "titulo": "RESUMEN DE FICHA CLÍNICA"},
    "centro_c": {"color": "#5b3a29", "fuente": "Verdana, Geneva, sans-serif", "titulo": "COPIA DE REGISTRO CLÍNICO AMBULATORIO"},
}


def construir_caso(rng: random.Random, indice: int) -> dict:
    """Arma un caso sintético completo: centros, valores, e ilegibilidad."""
    paciente_ref = f"PAC-{9000 + indice:04d}"
    centros = rng.sample(["centro_a", "centro_b", "centro_c"], k=rng.choice([2, 3]))
    # Se garantiza que centro_a y centro_c convivan en al menos la mitad de
    # los casos: es el par con conversión real de unidad de leucocitos
    # (/mm³ vs 10³/µL). Si el sorteo no los incluyó a ambos, se fuerza.
    if indice % 2 == 0 and not {"centro_a", "centro_c"}.issubset(set(centros)):
        centros = sorted({"centro_a", "centro_c", centros[0]})

    valores_base = generar_valores(rng)  # reutiliza generador/generar_ficha_pdf.py

    # El primer caso SIEMPRE lleva un campo ilegible (garantiza cobertura del
    # camino de campos_ilegibles sin depender del azar). Los demás, con 35%.
    tiene_ilegible = (indice == 0) or (rng.random() < 0.35)
    centro_ilegible = rng.choice(centros) if tiene_ilegible else None

    return {
        "caso_id": f"CASO-{indice:04d}",
        "paciente_ref": paciente_ref,
        "centros": centros,
        "valores_base": valores_base,
        "centro_ilegible": centro_ilegible,
        "analito_ilegible": ANALITO_ILEGIBLE if tiene_ilegible else None,
    }


def valor_mostrado(analito: str, centro: str, valores_base: dict, ilegible: bool):
    """Valor tal como debe aparecer en el HTML del centro. None si es ilegible."""
    if ilegible:
        return None
    return formatear_valor(analito, valores_base[analito], centro)


def valor_canonico_de(analito: str, valores_base: dict):
    """El valor canónico real (independiente del centro): mg/dL, g/dL o 10³/µL."""
    crudo = valores_base[analito]
    if analito == "leucocitos":
        return round(crudo / 1000, 2)
    return crudo


def fuera_de_rango(analito: str, valor_can) -> bool:
    if valor_can is None:
        return None
    lo, hi = ANALITOS_CANONICOS[analito]["rango"]
    return not (lo <= valor_can <= hi)


def construir_registro_verdad(caso: dict, centro: str, nombre_archivo: str) -> dict:
    """Registro 'perfecto' para un documento, en el formato del schema wiki-salud."""
    vocab = ANALITO_VOCAB[centro]
    paciente_ref = caso["paciente_ref"]
    ilegible_aca = caso["centro_ilegible"] == centro

    diagnosticos = []
    for clave, dg in DIAGNOSTICOS.items():
        diagnosticos.append({
            "fecha": None,
            "nombre_original": dg["por_centro"][centro],
            "nombre_canonico": dg["canonico"],
            "estado": dg["estado"],
            "confianza": "alta",
        })

    medicamentos = []
    for clave, med in MEDICAMENTOS.items():
        m = med["por_centro"][centro]
        medicamentos.append({
            "nombre_original": m["nombre"],
            "principio_activo": med["principio_activo"],
            "dosis": m["dosis"],
            "frecuencia": m["frecuencia"],
            "vigente": True,
            "confianza": "alta",
        })

    analitos = []
    campos_ilegibles = []
    for analito_key, (nombre_mostrado, unidad, rango_ref) in vocab["analitos"].items():
        es_ilegible = ilegible_aca and analito_key == caso["analito_ilegible"]
        valor = valor_mostrado(analito_key, centro, caso["valores_base"], es_ilegible)
        canon = ANALITOS_CANONICOS[analito_key]

        if es_ilegible:
            analitos.append({
                "nombre_original": nombre_mostrado,
                "nombre_canonico": canon["nombre_canonico"],
                "valor": None,
                "unidad": None,
                "valor_canonico": None,
                "unidad_canonica": None,
                "rango_referencia": rango_ref,
                "fuera_de_rango": None,
                "confianza": "baja",
            })
            campos_ilegibles.append(
                f"{nombre_mostrado} ({vocab['nombre_centro']}) — valor ilegible en el documento original"
            )
            continue

        valor_can = valor_canonico_de(analito_key, caso["valores_base"])
        analitos.append({
            "nombre_original": nombre_mostrado,
            "nombre_canonico": canon["nombre_canonico"],
            "valor": valor,
            "unidad": unidad,
            "valor_canonico": valor_can,
            "unidad_canonica": canon["unidad_canonica"],
            "rango_referencia": rango_ref,
            "fuera_de_rango": fuera_de_rango(analito_key, valor_can),
            "confianza": "alta",
        })

    return {
        "paciente_ref": paciente_ref,
        "centro_origen": vocab["nombre_centro"],
        "documento_ref": nombre_archivo,
        "extraccion_fallida": False,
        "diagnosticos": diagnosticos,
        "alergias": [],
        "medicamentos": medicamentos,
        "atenciones": [],
        "procedimientos": [],
        "imagenes": [],
        "examenes": [{
            "fecha": None,
            "tipo_examen": "Laboratorio general",
            "analitos": analitos,
        }],
        "campos_ilegibles": campos_ilegibles,
        "notas_extraccion": "",
    }


def render_ficha_html(caso: dict, centro: str) -> str:
    """HTML de la ficha de `centro` para `caso`, con envoltura importada."""
    vocab = ANALITO_VOCAB[centro]
    estilo = CENTROS_ESTILO[centro]
    paciente_ref = caso["paciente_ref"]
    ilegible_aca = caso["centro_ilegible"] == centro

    cabecera = f"""
<div class="cab">
  <h1>{vocab['nombre_centro']}</h1>
  <p>{vocab['direccion']}</p>
  <p>{estilo['titulo']}</p>
</div>
<div class="datos">
  <div><b>Paciente (ref.):</b> {paciente_ref}</div>
  <div><b>Centro:</b> {centro}</div>
</div>"""

    filas_dg = "".join(
        f"<tr><td>{dg['por_centro'][centro]}</td><td>Activo</td></tr>"
        for dg in DIAGNOSTICOS.values()
    )
    filas_med = "".join(
        f"<tr><td>{med['por_centro'][centro]['nombre']}</td>"
        f"<td>{med['por_centro'][centro]['dosis']}</td>"
        f"<td>{med['por_centro'][centro]['frecuencia']}</td></tr>"
        for med in MEDICAMENTOS.values()
    )

    filas_lab = ""
    for analito_key, (nombre_mostrado, unidad, rango_ref) in vocab["analitos"].items():
        es_ilegible = ilegible_aca and analito_key == caso["analito_ilegible"]
        if es_ilegible:
            filas_lab += f"<tr><td>{nombre_mostrado}</td><td>—(*)</td><td>{unidad}</td><td>{rango_ref}</td></tr>"
        else:
            valor = valor_mostrado(analito_key, centro, caso["valores_base"], False)
            filas_lab += f"<tr><td>{nombre_mostrado}</td><td>{valor}</td><td>{unidad}</td><td>{rango_ref}</td></tr>"

    nota_ilegible = (
        "<p class='prosa'>(*) Valor manchado/no legible en el documento original.</p>"
        if ilegible_aca else ""
    )

    cuerpo = f"""
<h2>Antecedentes mórbidos</h2>
<table><tr><th>Diagnóstico</th><th>Estado</th></tr>{filas_dg}</table>

<h2>Fármacos en uso</h2>
<table><tr><th>Producto</th><th>Dosis</th><th>Posología</th></tr>{filas_med}</table>

<h2>Laboratorio</h2>
<table><tr><th>Analito</th><th>Valor</th><th>Unidad</th><th>Referencia</th></tr>{filas_lab}</table>
{nota_ilegible}"""

    return envoltura(
        f"Ficha Clínica — {vocab['nombre_centro']} — {paciente_ref}",
        estilo["color"], estilo["fuente"], cabecera, cuerpo,
    )


def escribir_caso(caso: dict, destino: Path) -> dict:
    """Escribe las fichas HTML y verdad.json de un caso. Devuelve su entrada de índice."""
    carpeta = destino / caso["caso_id"]
    carpeta.mkdir(parents=True, exist_ok=True)

    documentos = {}
    archivos = []
    for centro in caso["centros"]:
        nombre_archivo = f"ficha-{centro}.html"
        html = render_ficha_html(caso, centro)
        (carpeta / nombre_archivo).write_text(html, encoding="utf-8")
        documentos[nombre_archivo] = construir_registro_verdad(caso, centro, nombre_archivo)
        archivos.append(nombre_archivo)

    canonico_esperado = {
        "diagnosticos": [
            {"nombre_canonico": dg["canonico"], "presente_en_centros": len(caso["centros"])}
            for dg in DIAGNOSTICOS.values()
        ],
        "medicamentos": [
            {"principio_activo": med["principio_activo"], "presente_en_centros": len(caso["centros"])}
            for med in MEDICAMENTOS.values()
        ],
        "examenes_analitos": [
            {
                "nombre_canonico": ANALITOS_CANONICOS[k]["nombre_canonico"],
                "unidad_canonica": ANALITOS_CANONICOS[k]["unidad_canonica"],
                "valor_canonico": (
                    None if (caso["centro_ilegible"] and k == caso["analito_ilegible"]
                              and caso["centro_ilegible"] in caso["centros"])
                    else valor_canonico_de(k, caso["valores_base"])
                ),
            }
            for k in ANALITOS_CANONICOS
        ],
    }

    verdad = {
        "caso_id": caso["caso_id"],
        "paciente_ref": caso["paciente_ref"],
        "centros": caso["centros"],
        "descripcion": (
            "Casos difíciles presentes: conversión de unidades de leucocitos "
            "(si incluye centro_a y centro_c), nombre comercial vs. principio "
            "activo (losartán), mismo analito con nombre distinto por centro"
            + (f", valor ilegible en {caso['centro_ilegible']} ({caso['analito_ilegible']})"
               if caso["centro_ilegible"] else "") + "."
        ),
        "documentos": documentos,
        "canonico_esperado": canonico_esperado,
    }

    (carpeta / "verdad.json").write_text(
        json.dumps(verdad, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "caso_id": caso["caso_id"],
        "paciente_ref": caso["paciente_ref"],
        "centros": caso["centros"],
        "archivos": archivos,
        "tiene_ilegible": caso["centro_ilegible"] is not None,
        "carpeta": caso["caso_id"],
    }


def main():
    ap = argparse.ArgumentParser(
        description="Genera un dataset de testing reproducible con verdad de referencia."
    )
    ap.add_argument("--seed", type=int, default=42, help="Semilla del generador aleatorio (default: 42)")
    ap.add_argument("--n", type=int, default=6, help="Cantidad de casos a generar (default: 6)")
    ap.add_argument("--out", type=str, default=str(SALIDA_DEFAULT), help="Carpeta de salida (default: pruebas/dataset)")
    args = ap.parse_args()

    destino = Path(args.out)
    destino.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    indice_general = []
    for i in range(args.n):
        caso = construir_caso(rng, i)
        entrada = escribir_caso(caso, destino)
        indice_general.append(entrada)
        print(f"  {entrada['caso_id']}: {caso['paciente_ref']} — centros {caso['centros']}"
              f"{' — con campo ilegible' if entrada['tiene_ilegible'] else ''}")

    (destino / "INDICE.json").write_text(
        json.dumps({
            "seed": args.seed,
            "n": args.n,
            "casos": indice_general,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n{args.n} caso(s) generado(s) en {destino} (seed={args.seed}).")
    print(f"Índice: {destino / 'INDICE.json'}")


if __name__ == "__main__":
    main()
