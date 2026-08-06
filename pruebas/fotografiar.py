"""Genera versiones fotografiadas de las fichas HTML del dataset — IMPACTLAB.

Por qué existe. `pruebas/dataset/` trae fichas HTML limpias. Un hospital
público real no manda HTML: manda una foto o un escaneo del papel. Este
script simula ese salto — HTML -> PDF limpio (Chrome headless) -> imagen
(PyMuPDF) -> degradación fotográfica (perspectiva, rotación, iluminación
despareja, blur, ruido, compresión JPEG) — para poder medir después si la
extracción con Claude sostiene la calidad sobre ese material degradado.

Es la versión "de producto" de la prueba de concepto validada a mano. Misma
técnica, reproducible y recorriendo todo el dataset en vez de un solo archivo.

Uso:
    python pruebas/fotografiar.py
    python pruebas/fotografiar.py --dureza dura
    python pruebas/fotografiar.py --solo CASO-0000 --seed 7

Salida por defecto: pruebas/dataset_fotos/CASO-XXXX/ficha-<centro>.jpg y .pdf
"""

import argparse
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

AQUI = Path(__file__).resolve().parent
DATASET_DEFAULT = AQUI / "dataset"
SALIDA_DEFAULT = AQUI / "dataset_fotos"

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

NIVELES = {
    "suave": dict(rot=0.6, blur=0.4, ruido=3, calidad=80),
    "media": dict(rot=1.6, blur=0.8, ruido=7, calidad=60),
    "dura":  dict(rot=3.0, blur=1.3, ruido=13, calidad=38),
}


# ---------------------------------------------------------------------------
# HTML -> PDF limpio, vía Chrome headless.
# ---------------------------------------------------------------------------
def html_a_pdf(ruta_html: Path, ruta_pdf: Path, user_data_dir: Path):
    """Convierte un HTML a PDF con Chrome headless.

    Rutas SIEMPRE absolutas: Chrome headless falla con "Acceso denegado" si
    --print-to-pdf apunta a una ruta relativa. --user-data-dir propio evita
    que Chrome intente reusar/lockear el perfil real del usuario.
    """
    if not CHROME.exists():
        sys.exit(f"No se encontró Chrome en {CHROME}")

    ruta_html = ruta_html.resolve()
    ruta_pdf = ruta_pdf.resolve()
    ruta_pdf.parent.mkdir(parents=True, exist_ok=True)

    comando = [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir={user_data_dir.resolve()}",
        f"--print-to-pdf={ruta_pdf}",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        ruta_html.as_uri(),
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True, timeout=60)
    if not ruta_pdf.exists():
        sys.exit(
            f"Chrome no generó {ruta_pdf}\n"
            f"stdout: {resultado.stdout}\nstderr: {resultado.stderr}"
        )


# ---------------------------------------------------------------------------
# PDF limpio -> foto degradada (misma técnica validada en fotografiar_prueba.py)
# ---------------------------------------------------------------------------
def pdf_a_imagen(ruta_pdf: Path, dpi=150) -> Image.Image:
    doc = fitz.open(ruta_pdf)
    pagina = doc[0]
    pix = pagina.get_pixmap(dpi=dpi)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def iluminacion_despareja(img, rng):
    ancho, alto = img.size
    cx, cy = rng.uniform(0.2, 0.8), rng.uniform(0.2, 0.8)
    ys, xs = np.mgrid[0:alto, 0:ancho]
    dist = np.sqrt(((xs / ancho) - cx) ** 2 + ((ys / alto) - cy) ** 2)
    mascara = 1.0 - 0.45 * (dist / dist.max())
    arr = np.asarray(img).astype(np.float32)
    arr *= mascara[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def perspectiva(img, rng):
    ancho, alto = img.size
    d = min(ancho, alto) * 0.02
    origen = [(0, 0), (ancho, 0), (ancho, alto), (0, alto)]
    destino = [(rng.uniform(0, d), rng.uniform(0, d)),
               (ancho - rng.uniform(0, d), rng.uniform(0, d)),
               (ancho - rng.uniform(0, d), alto - rng.uniform(0, d)),
               (rng.uniform(0, d), alto - rng.uniform(0, d))]
    matriz = []
    for (x, y), (u, v) in zip(destino, origen):
        matriz.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        matriz.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    A = np.matrix(matriz, dtype=float)
    B = np.array(origen).reshape(8)
    coef = np.array(np.linalg.solve(A, B)).reshape(8)
    return img.transform((ancho, alto), Image.PERSPECTIVE, coef, Image.BICUBIC,
                          fillcolor=(238, 236, 232))


def fotografiar_pdf(ruta_pdf: Path, ruta_jpg: Path, ruta_pdf_foto: Path,
                     semilla: int, dureza: str):
    rng = random.Random(semilla)
    img = pdf_a_imagen(ruta_pdf)
    niveles = NIVELES[dureza]

    img = perspectiva(img, rng)
    img = img.rotate(rng.uniform(-niveles["rot"], niveles["rot"]),
                      resample=Image.BICUBIC, fillcolor=(238, 236, 232))
    img = iluminacion_despareja(img, rng)
    img = img.filter(ImageFilter.GaussianBlur(niveles["blur"]))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.85, 0.95))

    arr = np.asarray(img).astype(np.float32)
    arr += np.random.default_rng(semilla).normal(0, niveles["ruido"], arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    img.save(ruta_jpg, "JPEG", quality=niveles["calidad"])
    Image.open(ruta_jpg).convert("RGB").save(ruta_pdf_foto, "PDF", resolution=150)


# ---------------------------------------------------------------------------
def procesar_caso(carpeta_caso: Path, destino_caso: Path, archivos_html: list,
                   dureza: str, seed: int, user_data_dir: Path):
    destino_caso.mkdir(parents=True, exist_ok=True)
    for i, nombre_html in enumerate(archivos_html):
        ruta_html = carpeta_caso / nombre_html
        stem = Path(nombre_html).stem  # ej: ficha-centro_a
        ruta_pdf_limpio = destino_caso / f"{stem}.limpio.pdf"
        ruta_jpg = destino_caso / f"{stem}.jpg"
        ruta_pdf_foto = destino_caso / f"{stem}.pdf"

        html_a_pdf(ruta_html, ruta_pdf_limpio, user_data_dir)
        # semilla distinta por archivo pero reproducible: seed base + índice
        fotografiar_pdf(ruta_pdf_limpio, ruta_jpg, ruta_pdf_foto,
                         semilla=seed + i, dureza=dureza)
        ruta_pdf_limpio.unlink()  # era un intermedio, no se conserva
        print(f"  {nombre_html} -> {ruta_jpg.name}, {ruta_pdf_foto.name}")


def main():
    ap = argparse.ArgumentParser(
        description="Genera versiones fotografiadas de las fichas HTML del dataset."
    )
    ap.add_argument("--dataset", type=str, default=str(DATASET_DEFAULT),
                     help="Carpeta del dataset original (default: pruebas/dataset)")
    ap.add_argument("--out", type=str, default=str(SALIDA_DEFAULT),
                     help="Carpeta de salida (default: pruebas/dataset_fotos)")
    ap.add_argument("--dureza", choices=["suave", "media", "dura"], default="media",
                     help="Nivel de degradación fotográfica (default: media)")
    ap.add_argument("--seed", type=int, default=42, help="Semilla base (default: 42)")
    ap.add_argument("--solo", type=str, default=None,
                     help="Procesar un solo caso, ej: CASO-0000")
    args = ap.parse_args()

    carpeta_dataset = Path(args.dataset).resolve()
    destino = Path(args.out).resolve()
    indice_path = carpeta_dataset / "INDICE.json"
    if not indice_path.exists():
        sys.exit(f"No se encontró {indice_path}. Corre antes: python pruebas/generar_dataset.py")

    import json
    indice = json.loads(indice_path.read_text(encoding="utf-8"))
    casos = indice["casos"]
    if args.solo:
        casos = [c for c in casos if c["caso_id"] == args.solo]
        if not casos:
            sys.exit(f"No existe el caso {args.solo} en {indice_path}")

    tmp_perfil = Path(tempfile.mkdtemp(prefix="chrome-headless-"))
    try:
        print(f"Fotografiando {len(casos)} caso(s), dureza={args.dureza}, seed={args.seed}")
        for entrada in casos:
            carpeta_caso = carpeta_dataset / entrada["carpeta"]
            destino_caso = destino / entrada["caso_id"]
            print(f"{entrada['caso_id']}:")
            procesar_caso(carpeta_caso, destino_caso, entrada["archivos"],
                          args.dureza, args.seed, tmp_perfil)
    finally:
        shutil.rmtree(tmp_perfil, ignore_errors=True)

    print(f"\nOK: fotos en {destino}")


if __name__ == "__main__":
    main()
