"""Empaqueta el entregable final para la persona — L11.

El paquete es lo que el titular se lleva y lo único que existe al final:
    paquete/
      wiki-salud.html      <- el wiki consolidado (con links a originales/)
      wiki.json            <- el dato estructurado, portable a otro sistema
      originales/          <- los documentos tal como los entregó cada centro

"Somos el cartero, no el archivo": después de entregar esto, nada queda del
lado del servicio.

Uso:
    python empaquetar.py --wiki demo/wiki.json --originales "demo/ficha-*.html" --out paquete-PAC-0006.zip
"""

import argparse
import glob
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RENDER = AQUI / "render" / "render_wiki.py"


def empaquetar(wiki_json: Path, originales: list[Path], salida: Path, sintetico: bool) -> None:
    registros = json.loads(wiki_json.read_text(encoding="utf-8"))

    # Verificación de integridad: cada documento_ref del wiki debe estar en el paquete.
    refs = {r.get("documento_ref", "") for r in registros}
    nombres = {p.name for p in originales}
    faltantes = refs - nombres
    if faltantes:
        print(f"ADVERTENCIA: referenciados en el wiki pero no incluidos: {faltantes}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp) / "paquete"
        (raiz / "originales").mkdir(parents=True)

        # 1. Los originales, tal cual llegaron.
        for doc in originales:
            shutil.copy2(doc, raiz / "originales" / doc.name)

        # 2. El dato estructurado.
        shutil.copy2(wiki_json, raiz / "wiki.json")

        # 3. El wiki renderizado (sus links "ver documento" apuntan a originales/).
        cmd = [sys.executable, str(RENDER), "--in", str(wiki_json), "--out", str(raiz / "wiki-salud.html")]
        if sintetico:
            cmd.append("--sintetico")
        subprocess.run(cmd, check=True)

        # 4. ZIP final.
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
            for archivo in sorted(raiz.rglob("*")):
                if archivo.is_file():
                    z.write(archivo, archivo.relative_to(raiz.parent))

    print(f"OK: paquete -> {salida} ({salida.stat().st_size} bytes)")


def main():
    ap = argparse.ArgumentParser(description="Arma el paquete final del titular")
    ap.add_argument("--wiki", required=True, help="wiki.json (salida de la extracción)")
    ap.add_argument("--originales", nargs="+", required=True, help="Documentos originales (archivos o glob)")
    ap.add_argument("--out", required=True, help="Ruta del ZIP de salida")
    ap.add_argument("--sintetico", action="store_true", help="Marca el wiki como datos sintéticos")
    args = ap.parse_args()

    docs = []
    for patron in args.originales:
        docs.extend(Path(p) for p in glob.glob(patron))
    if not docs:
        sys.exit("No se encontró ningún documento original.")

    empaquetar(Path(args.wiki), docs, Path(args.out), args.sintetico)


if __name__ == "__main__":
    main()
