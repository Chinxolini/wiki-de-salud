"""Sella el pie de la web con la fecha y hora del despliegue.

Se corre justo antes de commitear lo que se va a desplegar:

    python tools/sellar_version.py

Escribe la fecha y hora local en el sello del pie de `entrada/index.html`. El commit
no se puede sellar acá -todavia no existe cuando se escribe el archivo-, asi que ese
lo informa `/api/version` en runtime y la pagina lo muestra al lado.

Con `--sha <sha>` se puede fijar ademas el commit esperado (util despues de commitear,
si se quiere que la pagina avise cuando el navegador sirve una copia cacheada).
"""
import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAGINA = RAIZ / "entrada" / "index.html"


def sellar(sha: str | None) -> None:
    html = PAGINA.read_text(encoding="utf-8")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    nuevo, n = re.subn(
        r'(<span id="selloFecha">)versión [^<]*(</span>)',
        rf"\g<1>versión {ahora}\g<2>",
        html,
    )
    if n != 1:
        sys.exit("No se encontró el sello en entrada/index.html (¿cambió el marcador?).")

    if sha:
        nuevo, m = re.subn(
            r'const SHA_SELLADO = "[^"]*";',
            f'const SHA_SELLADO = "{sha[:7]}";',
            nuevo,
        )
        if m != 1:
            sys.exit("No se encontró SHA_SELLADO en entrada/index.html.")

    PAGINA.write_text(nuevo, encoding="utf-8")
    print(f"Sellado: versión {ahora}" + (f" · {sha[:7]}" if sha else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description="Sella la versión en el pie de la web")
    ap.add_argument("--sha", default=None,
                    help="Commit esperado. 'HEAD' toma el commit actual del repo.")
    args = ap.parse_args()

    sha = args.sha
    if sha == "HEAD":
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ,
                             capture_output=True, text=True, check=True).stdout.strip()
    sellar(sha)


if __name__ == "__main__":
    main()
