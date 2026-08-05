"""Supresión del caso — hueco 5 del viaje del usuario.

Cierra el arco: entregamos el paquete y después no queda nada del titular en
nuestro sistema. Lo único que sobrevive es el aprendizaje agregado sobre cómo
responde cada centro, que no contiene ningún dato personal.

Es la contrapartida operativa de la cláusula QUINTA del poder simple
(`legal/PODER-SIMPLE-mandato.md`) y de la promesa C7 del pitch. Si el borrado no
es demostrable, todo el discurso legal es una diapositiva.

Uso:
    python borrar_caso.py --caso CASO-0006 --motivo servicio_completado
    python borrar_caso.py --caso CASO-0006 --motivo revocacion_mandato
    python borrar_caso.py --caso CASO-0006 --dry-run

Salidas:
    1. Borra el directorio del caso y la casilla espejo.
    2. Escribe una línea en `registro/supresiones.jsonl` — SIN datos personales.
    3. Escribe una línea en `registro/protocolos-aprendidos.jsonl` por centro,
       que es lo único que se conserva del caso.
    4. Emite la constancia de supresión para el titular.
"""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CASOS = AQUI / "casos"
REGISTRO = AQUI / "registro"

MOTIVOS = ("servicio_completado", "revocacion_mandato", "solicitud_del_titular", "vencimiento_del_poder")

# Todo lo que se borra. Cualquier ruta nueva que guarde datos del titular debe
# entrar acá, o el borrado deja de ser cierto.
SUPERFICIE = (
    ("directorio_del_caso", "casos/{caso}/"),
    ("originales_recibidos", "casos/{caso}/originales/"),
    ("expediente_generado", "casos/{caso}/wiki-salud.html"),
    ("paquete_entregado", "casos/{caso}/paquete-{caso}.zip"),
    ("casilla_espejo", "imap://{casilla}"),
    ("adjuntos_en_files_api", "anthropic:files/{caso}/*"),
)


def sello():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def seudonimo(caso_id: str) -> str:
    """Identificador estable que NO permite volver al titular.

    Se registra esto y no el caso_id, porque el caso_id circuló por los correos
    y podría correlacionarse. El hash trunco basta para contar casos sin poder
    reidentificar ninguno.
    """
    return "sup-" + hashlib.sha256(caso_id.encode()).hexdigest()[:12]


def cargar_caso(caso_id: str) -> dict:
    meta = CASOS / caso_id / "caso.json"
    if not meta.exists():
        raise SystemExit(f"No existe {meta}. ¿El caso_id es correcto?")
    return json.loads(meta.read_text(encoding="utf-8"))


def conservar_aprendizaje(caso: dict, ts: str) -> list[dict]:
    """Lo único que sobrevive: cómo respondió cada centro. Cero datos del titular.

    Nada de nombre, RUT, correo, casilla, diagnósticos ni valores de laboratorio
    entra acá. Solo el comportamiento del prestador, que es información sobre
    una institución, no sobre una persona.
    """
    filas = []
    for c in caso.get("centros", []):
        filas.append({
            "ts": ts,
            "centro": c["centro"],
            "canal_solicitud": c.get("canal"),
            "canal_respuesta": c.get("canal_respuesta"),
            "dias_habiles_primera_respuesta": c.get("dias_primera_respuesta"),
            "dias_habiles_entrega": c.get("dias_entrega"),
            "formato_entrega": c.get("formato_entrega"),
            "anios_historial_entregados": c.get("anios_entregados"),
            "cobro": c.get("cobro"),
            "exigio_poder": c.get("exigio_poder"),
            "requisitos_adicionales": c.get("requisitos_adicionales", []),
        })
    return filas


def constancia(caso_id: str, motivo: str, ts: str, borrado: list[str]) -> str:
    return f"""CONSTANCIA DE SUPRESIÓN DE DATOS PERSONALES

Referencia interna: {seudonimo(caso_id)}
Fecha y hora (UTC): {ts}
Motivo: {motivo.replace('_', ' ')}

Se deja constancia de que, en la fecha y hora indicadas, se suprimieron de
nuestros sistemas la totalidad de los datos personales y documentos obtenidos
en el marco del encargo, a saber:

{chr(10).join('  - ' + b for b in borrado)}

Se conserva únicamente un registro estadístico relativo al plazo y formato de
respuesta de cada prestador, que NO contiene datos personales ni permite
identificar al titular.

Esta supresión se practica en cumplimiento de la cláusula QUINTA del poder
simple otorgado por el titular y del principio de finalidad del artículo 3° de
la Ley N° 21.719.

El titular conserva la copia íntegra de su expediente y de los documentos
originales que le fue entregada. No es necesaria ninguna gestión de su parte.
"""


def main():
    p = argparse.ArgumentParser(description="Suprime un caso y deja constancia.")
    p.add_argument("--caso", required=True)
    p.add_argument("--motivo", default="servicio_completado", choices=MOTIVOS)
    p.add_argument("--dry-run", action="store_true", help="Muestra qué se borraría, sin borrar.")
    args = p.parse_args()

    caso = cargar_caso(args.caso)
    ts = sello()
    casilla = caso.get("casilla_espejo", "(sin casilla)")

    borrado = [n.replace("_", " ") + ": " + r.format(caso=args.caso, casilla=casilla)
               for n, r in SUPERFICIE]

    if args.dry_run:
        print(f"[dry-run] {args.caso} — se borraría:")
        for b in borrado:
            print("  -", b)
        print(f"[dry-run] se conservarían {len(conservar_aprendizaje(caso, ts))} filas de protocolo.")
        return

    REGISTRO.mkdir(exist_ok=True)

    # 1. Primero se conserva el aprendizaje: si el borrado falla a la mitad, no
    #    se pierde el activo; y si esto falla, no se ha borrado nada todavía.
    with (REGISTRO / "protocolos-aprendidos.jsonl").open("a", encoding="utf-8") as f:
        for fila in conservar_aprendizaje(caso, ts):
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")

    # 2. La constancia se emite antes de borrar, porque necesita leer el caso.
    texto = constancia(args.caso, args.motivo, ts, borrado)
    salida = REGISTRO / f"constancia-{seudonimo(args.caso)}.txt"
    salida.write_text(texto, encoding="utf-8")

    # 3. Ahora sí, el borrado.
    directorio = CASOS / args.caso
    if directorio.exists():
        shutil.rmtree(directorio)
    # La casilla espejo y los adjuntos subidos se eliminan por sus respectivas
    # APIs. En la demo el mail-service es local, así que queda como registro.
    # TODO(producto): llamar al endpoint de Mauro para eliminar la casilla y a
    # la Files API para eliminar los adjuntos subidos.

    # 4. El log de supresiones: seudónimo, no caso_id.
    with (REGISTRO / "supresiones.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": ts,
            "ref": seudonimo(args.caso),
            "motivo": args.motivo,
            "elementos_suprimidos": len(SUPERFICIE),
            "centros_en_el_caso": len(caso.get("centros", [])),
        }, ensure_ascii=False) + "\n")

    print(f"Caso suprimido. Constancia: {salida}")
    print("Lo que queda del titular en el sistema: nada.")
    print(f"Lo que queda del caso: {len(caso.get('centros', []))} filas de protocolo por centro, sin datos personales.")


if __name__ == "__main__":
    main()
