"""Mide si la extracción con Claude sostiene calidad sobre fotos vs. HTML — IMPACTLAB.

Por qué existe. Un hospital público no manda HTML: manda una foto de un
papel. `pruebas/fotografiar.py` genera esa versión degradada. Este script
corre `extraccion/extraer.py` (función `extraer`, sin reimplementarla) sobre
la ficha HTML original Y sobre su foto correspondiente, y compara ambas
extracciones contra `verdad.json` con el evaluador de `pruebas/evaluar.py`
(tampoco reimplementado). La salida es una tabla HTML vs. foto por dureza y
categoría, más la lista de campos donde la foto perdió información respecto
del HTML.

Por defecto NO llama a la API: solo dice qué haría (cuántas llamadas, qué
archivos, costo aproximado en llamadas). Gastar tokens requiere `--con-api`
explícito.

Uso:
    python pruebas/medir_ocr.py --dureza media                       # dry-run
    python pruebas/medir_ocr.py --con-api --dureza media \
        --casos CASO-0000 CASO-0001                                  # real
"""

import argparse
import json
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))

DATASET_DEFAULT = AQUI / "dataset"
FOTOS_DEFAULT = AQUI / "dataset_fotos"

MODELO_DEFAULT = "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# Carga de ANTHROPIC_API_KEY desde .env del repo, si no está en el entorno.
# Parseo manual (sin dotenv, regla del proyecto: solo stdlib + lo ya usado).
# Nunca se imprime la clave.
# ---------------------------------------------------------------------------
def cargar_api_key_de_env():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    ruta_env = RAIZ / ".env"
    if not ruta_env.exists():
        return
    for linea in ruta_env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave == "ANTHROPIC_API_KEY" and valor:
            os.environ["ANTHROPIC_API_KEY"] = valor
            return


# ---------------------------------------------------------------------------
def cargar_casos(dataset: Path, fotos: Path, seleccion):
    indice = json.loads((dataset / "INDICE.json").read_text(encoding="utf-8"))
    casos = indice["casos"]
    if seleccion:
        casos = [c for c in casos if c["caso_id"] in seleccion]
    salida = []
    for c in casos:
        verdad = json.loads((dataset / c["carpeta"] / "verdad.json").read_text(encoding="utf-8"))
        salida.append({"entrada": c, "verdad": verdad})
    return salida


def ruta_foto_de(fotos: Path, caso_id: str, nombre_html: str) -> Path:
    stem = Path(nombre_html).stem
    return fotos / caso_id / f"{stem}.jpg"


def centro_de(nombre_html: str, verdad_doc: dict) -> str:
    return verdad_doc.get("centro_origen") or Path(nombre_html).stem


# ---------------------------------------------------------------------------
def plan_de_llamadas(casos, fotos: Path):
    """Lista de (caso_id, nombre_html, existe_foto) sin llamar a nada."""
    plan = []
    for c in casos:
        caso_id = c["entrada"]["caso_id"]
        for nombre_html, doc_verdad in c["verdad"]["documentos"].items():
            ruta_foto = ruta_foto_de(fotos, caso_id, nombre_html)
            plan.append((caso_id, nombre_html, doc_verdad, ruta_foto, ruta_foto.exists()))
    return plan


def mostrar_dry_run(plan, dureza):
    print(f"DRY-RUN — no se llama a la API (falta --con-api).\n")
    print(f"Dureza objetivo: {dureza}")
    print(f"Documentos a procesar: {len(plan)} (cada uno = 2 llamadas: HTML + foto)")
    faltan = [p for p in plan if not p[4]]
    for caso_id, nombre_html, _, ruta_foto, existe in plan:
        marca = "OK" if existe else "FALTA FOTO"
        print(f"  [{marca}] {caso_id}/{nombre_html} <-> {ruta_foto.relative_to(RAIZ)}")
    if faltan:
        print(f"\nAVISO: {len(faltan)} foto(s) no existen. Corré antes:")
        print(f"  python pruebas/fotografiar.py --dureza {dureza}")
    print(f"\nTotal de llamadas si se corre con --con-api: {len(plan) * 2}")


# ---------------------------------------------------------------------------
def correr_extraccion(plan, modelo, dureza):
    """Ejecuta extraccion/extraer.extraer() sobre HTML y foto de cada documento.

    Devuelve dos listas de (verdad_doc, registro_extraido): una para HTML,
    otra para foto. documento_ref/paciente_ref del registro se sobreescriben
    con los valores conocidos del caso, porque el nombre de archivo cambia
    entre HTML y foto (.html vs .jpg) y no debe afectar el emparejamiento con
    verdad.json: lo que se está midiendo es la extracción, no el nombre.
    """
    import anthropic
    from extraccion.extraer import extraer

    client = anthropic.Anthropic()
    resultados_html, resultados_foto = [], []

    for caso_id, nombre_html, doc_verdad, ruta_foto, existe_foto in plan:
        if not existe_foto:
            print(f"AVISO: falta {ruta_foto}, se omite {caso_id}/{nombre_html}", file=sys.stderr)
            continue

        paciente_ref = doc_verdad["paciente_ref"]
        centro = centro_de(nombre_html, doc_verdad)
        ruta_html = DATASET_DEFAULT / caso_id / nombre_html

        print(f"-- {caso_id}/{nombre_html} --", file=sys.stderr)
        print("  HTML:", file=sys.stderr)
        reg_html = extraer(client, ruta_html, centro, paciente_ref, modelo)
        reg_html["documento_ref"] = nombre_html
        reg_html["paciente_ref"] = paciente_ref
        resultados_html.append((doc_verdad, reg_html))

        print("  FOTO:", file=sys.stderr)
        reg_foto = extraer(client, ruta_foto, centro, paciente_ref, modelo)
        reg_foto["documento_ref"] = nombre_html
        reg_foto["paciente_ref"] = paciente_ref
        resultados_foto.append((doc_verdad, reg_foto))

    return resultados_html, resultados_foto


# ---------------------------------------------------------------------------
def agregar(pares):
    from pruebas.evaluar import comparar_caso
    agregado = {
        "diagnosticos_ok": 0, "diagnosticos_total": 0, "diagnosticos_fp": 0,
        "medicamentos_ok": 0, "medicamentos_total": 0, "medicamentos_fp": 0,
        "analitos_ok": 0, "analitos_total": 0, "analitos_fp": 0,
    }
    detalle = []
    for doc_verdad, registro in pares:
        m = comparar_caso(doc_verdad, registro)
        for k in agregado:
            agregado[k] += m[k]
        detalle.append((doc_verdad, registro, m))
    return agregado, detalle


def pct(ok, total):
    return f"{ok}/{total} ({100 * ok / total:.1f}%)" if total else "sin datos"


def campos_perdidos(detalle_html, detalle_foto):
    """Compara detalle a detalle: qué campo acertó el HTML y perdió la foto."""
    perdidos = []
    idx_foto = {
        (d["documento_ref"], r.get("documento_ref")): (d, r, m) for d, r, m in detalle_foto
    }
    # Emparejamos por posición porque documento_ref es igual en ambos (se
    # sobreescribió arriba); recorremos ambas listas en paralelo.
    for (dv_h, rh, mh), (dv_f, rf, mf) in zip(detalle_html, detalle_foto):
        etiqueta = f"{dv_h.get('centro_origen')} / {rh.get('documento_ref')}"

        dg_h = {d["nombre_canonico"].strip().lower() for d in rh.get("diagnosticos", [])}
        dg_f = {d["nombre_canonico"].strip().lower() for d in rf.get("diagnosticos", [])}
        for perdido in dg_h - dg_f:
            perdidos.append(f"{etiqueta}: diagnóstico '{perdido}' salió en HTML, no en foto")

        med_h = {d["principio_activo"].strip().lower() for d in rh.get("medicamentos", [])}
        med_f = {d["principio_activo"].strip().lower() for d in rf.get("medicamentos", [])}
        for perdido in med_h - med_f:
            perdidos.append(f"{etiqueta}: medicamento '{perdido}' salió en HTML, no en foto")

        an_h = {a["nombre_canonico"].strip().lower(): a for e in rh.get("examenes", []) for a in e.get("analitos", [])}
        an_f = {a["nombre_canonico"].strip().lower(): a for e in rf.get("examenes", []) for a in e.get("analitos", [])}
        for nombre, av in an_h.items():
            af = an_f.get(nombre)
            if af is None:
                perdidos.append(f"{etiqueta}: analito '{nombre}' salió en HTML, no en foto")
            elif av.get("valor_canonico") is not None and af.get("valor_canonico") is None:
                perdidos.append(f"{etiqueta}: analito '{nombre}' con valor en HTML, null en foto")
            elif av.get("valor_canonico") is not None and af.get("valor_canonico") is not None:
                try:
                    if abs(float(av["valor_canonico"]) - float(af["valor_canonico"])) > 0.05:
                        perdidos.append(
                            f"{etiqueta}: analito '{nombre}' valor distinto "
                            f"(HTML={av['valor_canonico']} foto={af['valor_canonico']})"
                        )
                except (TypeError, ValueError):
                    pass
    return perdidos


def mostrar_tabla(nombre, agregado_html, agregado_foto):
    print(f"\n{'=' * 72}\n{nombre}\n{'=' * 72}")
    filas = [
        ("Diagnósticos", "diagnosticos"),
        ("Medicamentos", "medicamentos"),
        ("Analitos", "analitos"),
    ]
    print(f"{'Categoría':<15}{'HTML':<28}{'Foto':<28}")
    for etiqueta, clave in filas:
        h = pct(agregado_html[f"{clave}_ok"], agregado_html[f"{clave}_total"])
        f = pct(agregado_foto[f"{clave}_ok"], agregado_foto[f"{clave}_total"])
        print(f"{etiqueta:<15}{h:<28}{f:<28}")
    print(f"\nFalsos positivos — HTML: dg={agregado_html['diagnosticos_fp']} "
          f"med={agregado_html['medicamentos_fp']} analitos={agregado_html['analitos_fp']}")
    print(f"Falsos positivos — Foto: dg={agregado_foto['diagnosticos_fp']} "
          f"med={agregado_foto['medicamentos_fp']} analitos={agregado_foto['analitos_fp']}")


def main():
    ap = argparse.ArgumentParser(
        description="Compara extracción sobre HTML vs. foto contra la verdad de referencia."
    )
    ap.add_argument("--dataset", type=str, default=str(DATASET_DEFAULT))
    ap.add_argument("--fotos", type=str, default=str(FOTOS_DEFAULT))
    ap.add_argument("--dureza", choices=["suave", "media", "dura"], default="media",
                     help="Solo informativo acá (identifica qué corrida de fotografiar.py se usa)")
    ap.add_argument("--casos", nargs="*", default=None, help="Subconjunto de CASO-XXXX a correr")
    ap.add_argument("--modelo", default=MODELO_DEFAULT)
    ap.add_argument("--con-api", action="store_true",
                     help="Requerido para llamar de verdad a la API. Sin esto, solo dry-run.")
    ap.add_argument("--salida", type=str, default=None,
                     help="Si se pasa, guarda ahí un JSON con extracciones y métricas crudas")
    args = ap.parse_args()

    dataset = Path(args.dataset)
    fotos = Path(args.fotos)

    casos = cargar_casos(dataset, fotos, args.casos)
    if not casos:
        sys.exit("No hay casos que procesar (revisá --casos y el dataset).")

    plan = plan_de_llamadas(casos, fotos)

    if not args.con_api:
        mostrar_dry_run(plan, args.dureza)
        return

    cargar_api_key_de_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY (ni en el entorno ni en .env).")

    resultados_html, resultados_foto = correr_extraccion(plan, args.modelo, args.dureza)

    agregado_html, detalle_html = agregar(resultados_html)
    agregado_foto, detalle_foto = agregar(resultados_foto)

    mostrar_tabla(f"HTML vs. foto — dureza={args.dureza} — modelo={args.modelo}",
                  agregado_html, agregado_foto)

    perdidos = campos_perdidos(detalle_html, detalle_foto)
    print(f"\nCampos donde la foto perdió información respecto del HTML: {len(perdidos)}")
    for p in perdidos:
        print(f"  - {p}")

    if args.salida:
        crudo = {
            "dureza": args.dureza,
            "modelo": args.modelo,
            "agregado_html": agregado_html,
            "agregado_foto": agregado_foto,
            "campos_perdidos": perdidos,
            "extracciones_html": [r for _, r in resultados_html],
            "extracciones_foto": [r for _, r in resultados_foto],
        }
        Path(args.salida).write_text(json.dumps(crudo, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nCrudo guardado en {args.salida}")


if __name__ == "__main__":
    main()
