"""Extracción clínica con Claude — L4 + L5 del MVP.

Toma una ficha de laboratorio (PDF o HTML), la manda a Claude con el prompt de
extracción y el schema `wiki_salud`, y devuelve el JSON normalizado.

Uso:
    python extraer.py --entrada ../demo/ficha-centro_a.html --centro "Centro Médico San Rafael" --paciente PAC-0006
    python extraer.py --entrada ../demo/*.html --salida ../demo/wiki.json

Requiere ANTHROPIC_API_KEY en el entorno.
"""

import argparse
import base64
import glob
import json
import os
import sys
from pathlib import Path

import anthropic

# --- Rutas de los legos que este script consume -------------------------------
AQUI = Path(__file__).resolve().parent
PROMPT_EXTRACCION = AQUI.parent / "prompts" / "extraccion.md"
SCHEMA_WIKI_SALUD = AQUI.parent / "schemas" / "wiki-salud.schema.json"

# Modelo. Cambiar acá y en ningún otro lado.
MODELO = "claude-opus-5"
MAX_TOKENS = 16000


def cargar_legos():
    """Lee el prompt y el schema desde disco. Son los contratos, no se copian acá."""
    prompt = PROMPT_EXTRACCION.read_text(encoding="utf-8")
    schema = json.loads(SCHEMA_WIKI_SALUD.read_text(encoding="utf-8"))
    return prompt, schema


def bloque_documento(client, ruta: Path):
    """Devuelve el bloque de contenido para el documento.

    PDF  -> se sube a la Files API y se referencia por file_id (ruta A).
    HTML -> se manda como texto plano (las fichas sintéticas son HTML).
    Imagen -> se manda como bloque image en base64.
    """
    sufijo = ruta.suffix.lower()

    if sufijo == ".pdf":
        subido = client.beta.files.upload(
            file=(ruta.name, ruta.open("rb"), "application/pdf"),
            betas=["files-api-2025-04-14"],
        )
        return {"type": "document", "source": {"type": "file", "file_id": subido.id}}, subido.id

    if sufijo in (".png", ".jpg", ".jpeg"):
        medio = "image/png" if sufijo == ".png" else "image/jpeg"
        datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": medio, "data": datos},
        }, ruta.name

    # HTML o texto: va como texto. Claude lee la tabla igual.
    return {"type": "text", "text": ruta.read_text(encoding="utf-8")}, ruta.name


def extraer(client, ruta: Path, centro: str, paciente_ref: str) -> dict:
    """Una llamada a Claude por documento. Devuelve el registro `wiki_salud`."""
    prompt, schema = cargar_legos()
    bloque, doc_ref = bloque_documento(client, ruta)

    contexto = (
        f"Centro de origen: {centro}\n"
        f"Referencia del titular: {paciente_ref}\n"
        f"Referencia del documento: {doc_ref}\n"
    )

    respuesta = client.beta.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        betas=["files-api-2025-04-14"],
        system=[
            {
                "type": "text",
                "text": prompt,
                # El prompt es estable entre llamadas: se cachea.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": [{"type": "text", "text": contexto}, bloque]}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )

    texto = "".join(b.text for b in respuesta.content if b.type == "text")
    registro = json.loads(texto)

    # Log de uso: sirve para el screenshot de consola y para el control de costo.
    uso = respuesta.usage
    print(
        f"  {ruta.name}: in={uso.input_tokens} out={uso.output_tokens} "
        f"cache_w={getattr(uso, 'cache_creation_input_tokens', 0)} "
        f"cache_r={getattr(uso, 'cache_read_input_tokens', 0)}",
        file=sys.stderr,
    )
    return registro


# Mapeo de archivo de demo -> nombre del centro. Solo para la demo sintética.
CENTROS_DEMO = {
    "ficha-centro_a.html": "Centro Médico San Rafael",
    "ficha-centro_b.html": "Laboratorio Clínico Los Andes",
    "ficha-centro_c.html": "Red de Salud Cordillera",
}


def main():
    ap = argparse.ArgumentParser(description="Extrae datos clínicos con Claude")
    ap.add_argument("--entrada", nargs="+", required=True, help="Archivos o glob")
    ap.add_argument("--centro", default=None, help="Nombre del centro (si es un solo archivo)")
    ap.add_argument("--paciente", default="PAC-0006", help="Seudónimo del titular")
    ap.add_argument("--salida", default=None, help="JSON de salida. Si se omite, imprime a stdout")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY en el entorno.")

    rutas = []
    for patron in args.entrada:
        rutas.extend(Path(p) for p in glob.glob(patron))
    if not rutas:
        sys.exit("No se encontró ningún archivo de entrada.")

    client = anthropic.Anthropic()
    registros = []

    print(f"Extrayendo {len(rutas)} documento(s) con {MODELO}...", file=sys.stderr)
    for ruta in sorted(rutas):
        centro = args.centro or CENTROS_DEMO.get(ruta.name, ruta.stem)
        registros.append(extraer(client, ruta, centro, args.paciente))

    salida = json.dumps(registros, ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).write_text(salida, encoding="utf-8")
        print(f"OK: {len(registros)} registro(s) -> {args.salida}", file=sys.stderr)
    else:
        print(salida)


if __name__ == "__main__":
    main()
