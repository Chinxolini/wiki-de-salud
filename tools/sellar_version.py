"""Sella el pie de la web con la fecha y hora del despliegue.

Se corre justo antes de commitear lo que se va a desplegar:

    python tools/sellar_version.py

Escribe la fecha y hora local en el sello del pie de `entrada/index.html`. El commit
no se puede sellar acá -todavia no existe cuando se escribe el archivo-, asi que ese
lo informa `/api/version` en runtime y la pagina lo muestra al lado.

El commit no se sella en el HTML: hacerlo exige commitear, y ese commit cambia el sha,
asi que nunca calzaria. La pagina muestra el commit vivo al lado del sello y quien mira
compara.
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAGINA = RAIZ / "entrada" / "index.html"


def sellar() -> None:
    html = PAGINA.read_text(encoding="utf-8")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    nuevo, n = re.subn(
        r'(<span id="selloFecha">)versión [^<]*(</span>)',
        rf"\g<1>versión {ahora}\g<2>",
        html,
    )
    if n != 1:
        sys.exit("No se encontró el sello en entrada/index.html (¿cambió el marcador?).")


    PAGINA.write_text(nuevo, encoding="utf-8")
    print(f"Sellado: versión {ahora}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Sella la versión en el pie de la web")
    ap.parse_args()
    sellar()


if __name__ == "__main__":
    main()
