"""Evalúa la extracción clínica contra la verdad de referencia — IMPACTLAB.

Dos modos:
  --dry-run                     valida que pruebas/dataset/ es internamente
                                 coherente (fichas presentes, registros de
                                 verdad conformes al schema, convergencia
                                 canónica esperada). NO llama a la API.
  --extraccion archivo.json     compara una salida real de extraccion/extraer.py
                                 (lista de registros wiki_salud) contra la
                                 verdad de cada caso y emite métricas.

Por defecto no se gasta ningún token: llamar a la API real solo ocurre si el
usuario corre extraccion/extraer.py aparte y pasa su salida acá. La bandera
--con-api existe solo para dejarlo explícito y documentado; este script nunca
importa el cliente de Anthropic.

Uso:
    python pruebas/evaluar.py --dry-run
    python pruebas/evaluar.py --extraccion salida_extraccion.json
"""

import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
DATASET_DEFAULT = AQUI / "dataset"
SCHEMA_PATH = RAIZ / "schemas" / "wiki-salud.schema.json"

TOLERANCIA_VALOR = 0.05  # tolerancia numérica para valor_canonico (redondeos)


# ---------------------------------------------------------------------------
# Validador mínimo contra el schema. No es un validador JSON Schema genérico:
# cubre lo que wiki-salud.schema.json usa (object/array/enum/type-union), que
# alcanza para chequear que los registros de verdad.json son conformes.
# ---------------------------------------------------------------------------
def validar_contra_schema(instancia, esquema, ruta="$") -> list:
    errores = []
    tipos = esquema.get("type")
    if tipos:
        tipos = tipos if isinstance(tipos, list) else [tipos]
        if not _tipo_ok(instancia, tipos):
            errores.append(f"{ruta}: tipo esperado {tipos}, obtenido {type(instancia).__name__}")
            return errores  # sin el tipo correcto no tiene sentido seguir

    if "enum" in esquema and instancia is not None and instancia not in esquema["enum"]:
        errores.append(f"{ruta}: valor {instancia!r} no está en enum {esquema['enum']}")

    if isinstance(instancia, dict) and esquema.get("type") == "object":
        props = esquema.get("properties", {})
        for req in esquema.get("required", []):
            if req not in instancia:
                errores.append(f"{ruta}: falta el campo requerido '{req}'")
        if esquema.get("additionalProperties") is False:
            extra = set(instancia.keys()) - set(props.keys())
            if extra:
                errores.append(f"{ruta}: campos no declarados en el schema: {sorted(extra)}")
        for clave, subesquema in props.items():
            if clave in instancia:
                errores.extend(validar_contra_schema(instancia[clave], subesquema, f"{ruta}.{clave}"))

    if isinstance(instancia, list) and esquema.get("type") == "array":
        item_esquema = esquema.get("items")
        if item_esquema:
            for i, item in enumerate(instancia):
                errores.extend(validar_contra_schema(item, item_esquema, f"{ruta}[{i}]"))

    return errores


def _tipo_ok(valor, tipos_permitidos) -> bool:
    mapa = {
        "string": str, "number": (int, float), "integer": int,
        "boolean": bool, "array": list, "object": dict, "null": type(None),
    }
    for t in tipos_permitidos:
        py_tipo = mapa.get(t)
        if py_tipo is None:
            continue
        if t == "number" and isinstance(valor, bool):
            continue  # bool no cuenta como number aunque sea subclase de int
        if isinstance(valor, py_tipo):
            return True
    return False


# ---------------------------------------------------------------------------
# Carga del dataset
# ---------------------------------------------------------------------------
def cargar_dataset(carpeta: Path) -> list:
    indice_path = carpeta / "INDICE.json"
    if not indice_path.exists():
        sys.exit(f"No se encontró {indice_path}. Corre antes: python pruebas/generar_dataset.py")
    indice = json.loads(indice_path.read_text(encoding="utf-8"))
    casos = []
    for entrada in indice["casos"]:
        carpeta_caso = carpeta / entrada["carpeta"]
        verdad_path = carpeta_caso / "verdad.json"
        if not verdad_path.exists():
            print(f"AVISO: falta {verdad_path}, se omite el caso", file=sys.stderr)
            continue
        verdad = json.loads(verdad_path.read_text(encoding="utf-8"))
        casos.append({"carpeta": carpeta_caso, "verdad": verdad})
    return casos


# ---------------------------------------------------------------------------
# --dry-run: coherencia interna del dataset, sin API
# ---------------------------------------------------------------------------
def dry_run(carpeta: Path) -> bool:
    esquema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    casos = cargar_dataset(carpeta)
    if not casos:
        print("No hay casos que validar.")
        return False

    total_errores = 0
    con_ilegible = 0

    for caso in casos:
        v = caso["verdad"]
        caso_id = v["caso_id"]
        errores_caso = []

        # 1. Cada documento referenciado en verdad.json existe como archivo HTML.
        for nombre_archivo in v["documentos"]:
            if not (caso["carpeta"] / nombre_archivo).exists():
                errores_caso.append(f"falta el archivo HTML {nombre_archivo}")

        # 2. Cada registro de verdad conforma al schema wiki-salud.
        for nombre_archivo, registro in v["documentos"].items():
            errs = validar_contra_schema(registro, esquema)
            for e in errs:
                errores_caso.append(f"{nombre_archivo}: {e}")

        # 3. Convergencia canónica: mismo nombre_canonico / principio_activo
        #    en todos los documentos del caso (los "centros" describen a la
        #    misma persona, deben coincidir en lo canónico aunque no en el
        #    nombre original).
        canonicos_dg = {tuple(sorted(
            dg["nombre_canonico"] for dg in reg["diagnosticos"]
        )) for reg in v["documentos"].values()}
        if len(canonicos_dg) > 1:
            errores_caso.append(f"diagnósticos canónicos no convergen entre centros: {canonicos_dg}")

        canonicos_med = {tuple(sorted(
            m["principio_activo"] for m in reg["medicamentos"]
        )) for reg in v["documentos"].values()}
        if len(canonicos_med) > 1:
            errores_caso.append(f"principios activos no convergen entre centros: {canonicos_med}")

        # 4. Si hay campo ilegible, debe reflejarse en campos_ilegibles Y en
        #    el analito correspondiente (valor=null, confianza=baja).
        for nombre_archivo, registro in v["documentos"].items():
            analitos_ilegibles_marcados = [
                a for e in registro["examenes"] for a in e["analitos"] if a["valor"] is None
            ]
            if analitos_ilegibles_marcados and not registro["campos_ilegibles"]:
                errores_caso.append(f"{nombre_archivo}: hay analito con valor null pero campos_ilegibles vacío")
            if analitos_ilegibles_marcados:
                con_ilegible += 1

        if errores_caso:
            print(f"[FALLA] {caso_id}:")
            for e in errores_caso:
                print(f"    - {e}")
            total_errores += len(errores_caso)
        else:
            print(f"[OK]    {caso_id} — {len(v['documentos'])} documento(s), coherente")

    print("\n" + "-" * 66)
    if total_errores:
        print(f"DRY-RUN: {total_errores} error(es) en {len(casos)} caso(s).")
        return False
    print(f"DRY-RUN OK: {len(casos)} caso(s) coherentes. "
          f"{con_ilegible} documento(s) ejercitan el camino de campos_ilegibles.")
    return True


# ---------------------------------------------------------------------------
# --extraccion: comparación real contra verdad.json
# ---------------------------------------------------------------------------
def _normalizar(txt) -> str:
    return (txt or "").strip().lower()


def _valor_cerca(a, b) -> bool:
    if a is None or b is None:
        return a == b
    try:
        return abs(float(a) - float(b)) <= TOLERANCIA_VALOR
    except (TypeError, ValueError):
        return a == b


def emparejar_registros(extraccion: list, casos: list) -> dict:
    """Indexa la extracción por (paciente_ref, documento_ref) para poder
    encontrar, para cada documento de verdad, su registro extraído."""
    indice = {}
    for reg in extraccion:
        clave = (reg.get("paciente_ref"), reg.get("documento_ref"))
        indice[clave] = reg
    return indice


def comparar_caso(verdad_doc: dict, extraido: dict) -> dict:
    """Compara un documento de verdad contra su extracción. Devuelve conteos."""
    m = {
        "diagnosticos_ok": 0, "diagnosticos_total": 0, "diagnosticos_fp": 0,
        "medicamentos_ok": 0, "medicamentos_total": 0, "medicamentos_fp": 0,
        "analitos_ok": 0, "analitos_total": 0, "analitos_fp": 0,
    }

    dg_verdad = {_normalizar(d["nombre_canonico"]) for d in verdad_doc["diagnosticos"]}
    dg_extraido = {_normalizar(d.get("nombre_canonico")) for d in extraido.get("diagnosticos", [])}
    m["diagnosticos_total"] = len(dg_verdad)
    m["diagnosticos_ok"] = len(dg_verdad & dg_extraido)
    m["diagnosticos_fp"] = len(dg_extraido - dg_verdad)

    med_verdad = {_normalizar(x["principio_activo"]) for x in verdad_doc["medicamentos"]}
    med_extraido = {_normalizar(x.get("principio_activo")) for x in extraido.get("medicamentos", [])}
    m["medicamentos_total"] = len(med_verdad)
    m["medicamentos_ok"] = len(med_verdad & med_extraido)
    m["medicamentos_fp"] = len(med_extraido - med_verdad)

    analitos_verdad = [a for e in verdad_doc["examenes"] for a in e["analitos"]]
    analitos_extraidos = [a for e in extraido.get("examenes", []) for a in e.get("analitos", [])]
    idx_extraidos = {_normalizar(a.get("nombre_canonico")): a for a in analitos_extraidos}

    m["analitos_total"] = len(analitos_verdad)
    for av in analitos_verdad:
        ae = idx_extraidos.get(_normalizar(av["nombre_canonico"]))
        if ae is None:
            continue
        if av["valor_canonico"] is None:
            # caso ilegible: acierto si la extracción también lo marcó como
            # no legible (valor_canonico null), no si inventó un número.
            if ae.get("valor_canonico") is None:
                m["analitos_ok"] += 1
        else:
            if _valor_cerca(av["valor_canonico"], ae.get("valor_canonico")) and \
               _normalizar(av["unidad_canonica"]) == _normalizar(ae.get("unidad_canonica")):
                m["analitos_ok"] += 1
    nombres_verdad = {_normalizar(a["nombre_canonico"]) for a in analitos_verdad}
    m["analitos_fp"] = len({_normalizar(a.get("nombre_canonico")) for a in analitos_extraidos} - nombres_verdad)

    return m


def evaluar_convergencia(verdad: dict, indice_extraccion: dict) -> tuple:
    """De los documentos de un caso, ¿todos los extraídos coinciden en el
    nombre_canonico/principio_activo/valor_canonico? Devuelve (ok, total)."""
    registros_extraidos = []
    for nombre_archivo in verdad["documentos"]:
        clave = (verdad["paciente_ref"], nombre_archivo)
        if clave in indice_extraccion:
            registros_extraidos.append(indice_extraccion[clave])

    if len(registros_extraidos) < 2:
        return (0, 0)  # no hay nada que converger con un solo documento

    ok, total = 0, 0

    total += 1
    sets_dg = [{_normalizar(d.get("nombre_canonico")) for d in r.get("diagnosticos", [])} for r in registros_extraidos]
    if all(s == sets_dg[0] for s in sets_dg) and sets_dg[0]:
        ok += 1

    total += 1
    sets_med = [{_normalizar(m.get("principio_activo")) for m in r.get("medicamentos", [])} for r in registros_extraidos]
    if all(s == sets_med[0] for s in sets_med) and sets_med[0]:
        ok += 1

    total += 1
    valores_leuco = []
    for r in registros_extraidos:
        for e in r.get("examenes", []):
            for a in e.get("analitos", []):
                if _normalizar(a.get("nombre_canonico")) == "recuento de leucocitos" and a.get("valor_canonico") is not None:
                    valores_leuco.append(a["valor_canonico"])
    if len(valores_leuco) >= 2 and all(_valor_cerca(valores_leuco[0], v) for v in valores_leuco):
        ok += 1

    return (ok, total)


def evaluar_extraccion(carpeta: Path, archivo_extraccion: Path) -> bool:
    casos = cargar_dataset(carpeta)
    extraccion = json.loads(archivo_extraccion.read_text(encoding="utf-8"))
    if not isinstance(extraccion, list):
        sys.exit("El archivo de extracción debe ser una lista de registros wiki_salud "
                  "(la salida directa de extraccion/extraer.py).")

    indice_extraccion = emparejar_registros(extraccion, casos)

    agregado = {
        "diagnosticos_ok": 0, "diagnosticos_total": 0, "diagnosticos_fp": 0,
        "medicamentos_ok": 0, "medicamentos_total": 0, "medicamentos_fp": 0,
        "analitos_ok": 0, "analitos_total": 0, "analitos_fp": 0,
    }
    convergencia_ok, convergencia_total = 0, 0
    documentos_sin_match = 0

    for caso in casos:
        v = caso["verdad"]
        print(f"\n{v['caso_id']} ({v['paciente_ref']}):")
        for nombre_archivo, doc_verdad in v["documentos"].items():
            clave = (v["paciente_ref"], nombre_archivo)
            extraido = indice_extraccion.get(clave)
            if extraido is None:
                print(f"  {nombre_archivo}: SIN EXTRACCIÓN correspondiente (no se encontró "
                      f"paciente_ref={v['paciente_ref']!r} + documento_ref={nombre_archivo!r})")
                documentos_sin_match += 1
                continue
            m = comparar_caso(doc_verdad, extraido)
            for k in agregado:
                agregado[k] += m[k]
            print(f"  {nombre_archivo}: dg {m['diagnosticos_ok']}/{m['diagnosticos_total']} · "
                  f"med {m['medicamentos_ok']}/{m['medicamentos_total']} · "
                  f"analitos {m['analitos_ok']}/{m['analitos_total']} · "
                  f"falsos positivos: dg={m['diagnosticos_fp']} med={m['medicamentos_fp']} analitos={m['analitos_fp']}")

        ok, total = evaluar_convergencia(v, indice_extraccion)
        convergencia_ok += ok
        convergencia_total += total

    print("\n" + "=" * 66)
    print("AGREGADO")
    print("=" * 66)

    def pct(ok, total):
        return f"{ok}/{total} ({100 * ok / total:.1f}%)" if total else "sin datos"

    print(f"Diagnósticos correctos:  {pct(agregado['diagnosticos_ok'], agregado['diagnosticos_total'])}"
          f"  — falsos positivos: {agregado['diagnosticos_fp']}")
    print(f"Medicamentos correctos:  {pct(agregado['medicamentos_ok'], agregado['medicamentos_total'])}"
          f"  — falsos positivos: {agregado['medicamentos_fp']}")
    print(f"Analitos correctos:      {pct(agregado['analitos_ok'], agregado['analitos_total'])}"
          f"  — falsos positivos: {agregado['analitos_fp']}")
    print(f"Convergencia canónica entre centros: {pct(convergencia_ok, convergencia_total)}")
    if documentos_sin_match:
        print(f"\nAVISO: {documentos_sin_match} documento(s) de verdad.json no tuvieron "
              f"extracción correspondiente en {archivo_extraccion}.")

    return documentos_sin_match == 0


def main():
    ap = argparse.ArgumentParser(description="Evalúa una extracción contra la verdad de referencia del dataset.")
    ap.add_argument("--dataset", type=str, default=str(DATASET_DEFAULT), help="Carpeta del dataset (default: pruebas/dataset)")
    ap.add_argument("--dry-run", action="store_true", help="Solo valida coherencia interna del dataset, sin API")
    ap.add_argument("--extraccion", type=str, default=None, help="JSON con la salida de extraccion/extraer.py a evaluar")
    ap.add_argument("--con-api", action="store_true",
                     help="No usado por este script (nunca llama a la API); existe para dejarlo explícito en el default")
    args = ap.parse_args()

    if not args.dry_run and not args.extraccion:
        sys.exit("Elegí un modo: --dry-run, o --extraccion <archivo.json>.")

    carpeta = Path(args.dataset)

    if args.dry_run:
        ok = dry_run(carpeta)
        sys.exit(0 if ok else 1)

    ok = evaluar_extraccion(carpeta, Path(args.extraccion))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
