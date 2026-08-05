"""L9 — Cascada de verificación. Haiku extrae, un verificador coteja, el caso dudoso escala.

Por qué existe. La extracción de L4 corre con Haiku porque es ~20x más barata y
en las fichas de demo dio el mismo resultado que Opus. Pero las fichas de demo
son HTML limpio, y la realidad son PDF-imagen escaneados y cuadernos escritos a
mano. La pregunta que hace cualquier jurado es: "¿y cómo sabes que transcribió
bien?". Esta es la respuesta, y es un mecanismo, no una promesa.

Cómo funciona. Por cada valor extraído se le pide al verificador que lo busque
en el documento original y diga si coincide. El verificador NO ve la extracción
como verdad: recibe el documento y el valor afirmado, y responde si lo encuentra
tal cual, si difiere, o si no puede leerlo. Cuando el resultado no es limpio, el
documento completo se reextrae con un modelo mayor.

Qué NO hace. No juzga si el contenido clínico es suficiente, no interpreta y no
completa lo que no puede leer. Marca `ilegible` y ese campo llega al expediente
como ilegible, con su enlace al original. El juicio clínico es del médico
tratante, que verifica el dossier final contra los originales que van en el
paquete (L11).

Uso:
    python verificar.py --wiki ../demo/wiki.json --documentos "../demo/ficha-*.html"
    python verificar.py --wiki ../demo/wiki.json --documentos "../demo/*.html" --salida ../demo/wiki-verificado.json
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path

import anthropic

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from extraer import bloque_documento, extraer  # noqa: E402  (mismo lego, no se duplica)

# La escalera. Cada peldaño cuesta más y lee mejor.
EXTRACTOR = "claude-haiku-4-5"      # L4: el trabajo mecánico
VERIFICADOR = "claude-haiku-4-5"    # el cotejo, también barato: es una pregunta cerrada
ESCALON_1 = "claude-sonnet-5"       # discrepancias puntuales o confianza media
ESCALON_2 = "claude-opus-5"         # documento ilegible, manuscrito, o Sonnet tampoco cuadra

MAX_TOKENS = 8000

SYSTEM_VERIFICADOR = """Eres un verificador de transcripción. No eres un asistente clínico.

Recibes un documento de laboratorio y una lista de valores que otro sistema afirma
haber leído de él. Tu única tarea es decir, para cada valor afirmado, si el
documento efectivamente lo dice.

Para cada valor responde exactamente una de estas tres cosas:
- "coincide": el documento dice ese analito con ese valor y esa unidad.
- "difiere": el documento dice ese analito, pero con otro valor o unidad. Reporta
  lo que realmente dice.
- "ilegible": no puedes leer con certeza esa parte del documento, o el analito no
  aparece.

Reglas que no se rompen:
- No infieras. Si el documento está borroso, manuscrito o cortado, es "ilegible".
  Marcar "ilegible" es la respuesta correcta, no un fracaso.
- No corrijas valores clínicamente "raros". Un valor anómalo bien transcrito
  coincide.
- No conviertas unidades: compara lo que ves con lo afirmado. La conversión a
  unidad canónica la hace otro lego y se verifica aparte.
- No emitas juicios sobre la salud de la persona. No es tu tarea y está prohibido.

Devuelve solo el JSON pedido."""

SCHEMA_VERIFICACION = {
    "type": "object",
    "properties": {
        "resultados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "analito": {"type": "string"},
                    "valor_afirmado": {"type": "string"},
                    "veredicto": {"type": "string", "enum": ["coincide", "difiere", "ilegible"]},
                    "valor_en_documento": {
                        "type": "string",
                        "description": "Lo que el documento realmente dice. Cadena vacía si es ilegible.",
                    },
                    "nota": {"type": "string", "description": "Breve. Cadena vacía si no hay nada que decir."},
                },
                "required": ["analito", "valor_afirmado", "veredicto", "valor_en_documento", "nota"],
                "additionalProperties": False,
            },
        },
        "calidad_del_documento": {
            "type": "string",
            "enum": ["texto_limpio", "escaneo_legible", "escaneo_degradado", "manuscrito", "ilegible"],
        },
    },
    "required": ["resultados", "calidad_del_documento"],
    "additionalProperties": False,
}


def valores_de(registro: dict) -> list[dict]:
    """Aplana los analitos del registro wiki_salud para poder cotejarlos."""
    salida = []
    for r in registro.get("resultados", []):
        salida.append({
            "analito": r.get("analito_original") or r.get("analito_canonico", ""),
            "valor": f"{r.get('valor_original', '')} {r.get('unidad_original', '')}".strip(),
        })
    return salida


def verificar(client, ruta: Path, registro: dict) -> dict:
    valores = valores_de(registro)
    if not valores:
        return {"resultados": [], "calidad_del_documento": "ilegible"}

    bloque, _ = bloque_documento(client, ruta)
    afirmado = "\n".join(f"- {v['analito']}: {v['valor']}" for v in valores)

    r = client.beta.messages.create(
        model=VERIFICADOR,
        max_tokens=MAX_TOKENS,
        betas=["files-api-2025-04-14"],
        system=[{"type": "text", "text": SYSTEM_VERIFICADOR, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": [
            {"type": "text", "text": f"Valores afirmados por el extractor:\n{afirmado}"},
            bloque,
        ]}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA_VERIFICACION}},
    )
    u = r.usage
    print(f"  verificador in={u.input_tokens} out={u.output_tokens}", file=sys.stderr)
    return json.loads("".join(b.text for b in r.content if b.type == "text"))


def decidir(v: dict) -> tuple[str, str]:
    """La regla de escalamiento. Devuelve (accion, motivo).

    Es deliberadamente conservadora: cualquier discrepancia o ilegibilidad manda
    el documento a un modelo mayor. Un falso escalamiento cuesta centavos; un
    valor mal transcrito en un expediente de salud no.
    """
    res = v.get("resultados", [])
    calidad = v.get("calidad_del_documento", "ilegible")
    difieren = sum(1 for r in res if r["veredicto"] == "difiere")
    ilegibles = sum(1 for r in res if r["veredicto"] == "ilegible")

    if calidad in ("manuscrito", "ilegible"):
        return ESCALON_2, f"documento {calidad}"
    if ilegibles and calidad == "escaneo_degradado":
        return ESCALON_2, f"{ilegibles} campo(s) ilegible(s) sobre escaneo degradado"
    if difieren or ilegibles:
        return ESCALON_1, f"{difieren} discrepancia(s), {ilegibles} ilegible(s)"
    return "", "todos los valores coinciden"


def main():
    ap = argparse.ArgumentParser(description="L9 — verifica la extracción y escala si hace falta")
    ap.add_argument("--wiki", required=True, help="JSON producido por extraer.py")
    ap.add_argument("--documentos", nargs="+", required=True, help="Los originales, o glob")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--paciente", default="PAC-0006")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY en el entorno.")

    registros = json.loads(Path(args.wiki).read_text(encoding="utf-8"))
    rutas = sorted(Path(p) for patron in args.documentos for p in glob.glob(patron))
    if len(rutas) != len(registros):
        print(f"Aviso: {len(rutas)} documento(s) y {len(registros)} registro(s). "
              "Se emparejan por orden.", file=sys.stderr)

    client = anthropic.Anthropic()
    finales, auditoria = [], []

    for ruta, registro in zip(rutas, registros):
        print(f"{ruta.name}:", file=sys.stderr)
        v = verificar(client, ruta, registro)
        accion, motivo = decidir(v)

        if accion:
            print(f"  ESCALA a {accion} — {motivo}", file=sys.stderr)
            centro = registro.get("centro", ruta.stem)
            registro = extraer(client, ruta, centro, args.paciente, modelo=accion)
            estado = "reextraido"
        else:
            print(f"  OK — {motivo}", file=sys.stderr)
            estado = "verificado"

        registro["_verificacion"] = {
            "estado": estado,
            "modelo_extraccion": accion or EXTRACTOR,
            "modelo_verificador": VERIFICADOR,
            "calidad_documento": v.get("calidad_del_documento"),
            "motivo": motivo,
            "campos_ilegibles": [r["analito"] for r in v.get("resultados", [])
                                 if r["veredicto"] == "ilegible"],
        }
        finales.append(registro)
        auditoria.append({"documento": ruta.name, "accion": accion or "ninguna", "motivo": motivo,
                          "calidad": v.get("calidad_del_documento")})

    escalados = sum(1 for a in auditoria if a["accion"] != "ninguna")
    print(f"\n{len(finales)} documento(s): {len(finales)-escalados} verificados en Haiku, "
          f"{escalados} escalados.", file=sys.stderr)

    salida = json.dumps(finales, ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).write_text(salida, encoding="utf-8")
        Path(args.salida).with_suffix(".auditoria.json").write_text(
            json.dumps(auditoria, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"OK -> {args.salida}", file=sys.stderr)
    else:
        print(salida)


if __name__ == "__main__":
    main()
