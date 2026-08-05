"""L16 — Detección de incumplimiento y generación del reclamo.

La idea. El registro de protocolo por prestador (L14/L15) ya guarda cómo se portó
cada centro: cuánto demoró, en qué formato entregó, si cobró, si exigió poder
notarial. Esos mismos campos son los supuestos de infracción de la ley. Así que
el sistema que mide es el que detecta, y el que detecta puede redactar.

No denuncia solo. Detecta, arma el escrito y se lo propone al titular, que decide.
Denunciar en nombre de alguien sin que lo pida sería exactamente el abuso de
mandato que el propio poder prohíbe.

Uso:
    python denunciar.py --registro ../registro/protocolos-aprendidos.jsonl
    python denunciar.py --registro ../registro/protocolos-aprendidos.jsonl --centro RedSalud --emitir
"""

import argparse
import json
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# El régimen sancionatorio de la Ley 21.719 entra en vigencia el 1-dic-2026.
# Antes de esa fecha la vía es otra y las multas son ~200 veces menores: la
# ruta correcta depende de cuándo ocurre el incumplimiento, no de cuándo se
# escribió este código.
VIGENCIA_21719 = date(2026, 12, 1)

# Plazo de referencia. La Ley 20.584 no fija plazo ("sin dilaciones indebidas");
# la Superintendencia de Salud sugiere 10 días hábiles en su Monografía N°7
# (dic-2025). Desde dic-2026 el art. 11 de la 21.719 da 30 días corridos
# prorrogables por una sola vez.
PLAZO_SUGERIDO_HABILES = 10


# --- Los supuestos de infracción ---------------------------------------------
# Cada uno: (id, condición sobre la fila del registro, gravedad, fundamento).

def _sin_respuesta(f):
    d = f.get("dias_habiles_primera_respuesta")
    return d is None or d > PLAZO_SUGERIDO_HABILES

def _sin_entrega(f):
    return f.get("formato_entrega") == "sin_entrega" or f.get("dias_habiles_entrega") is None

def _formato_no_portable(f):
    return f.get("formato_entrega") in ("pdf_imagen", "imagen", "presencial")

def _cobro_indebido(f):
    return bool(f.get("cobro"))

def _poder_notarial_exigido(f):
    return any("notarial" in r.lower() for r in f.get("requisitos_adicionales", []))

def _sin_canal_publicado(f):
    return f.get("canal_solicitud") in (None, "", "presencial")


SUPUESTOS = [
    ("sin_respuesta_en_plazo", _sin_respuesta, "grave",
     "No responder la solicitud de acceso dentro de plazo razonable."),
    ("sin_entrega", _sin_entrega, "grave",
     "No entregar la copia de la ficha clínica solicitada."),
    ("formato_no_portable", _formato_no_portable, "grave",
     "Entregar en un formato que no es estructurado, de uso común ni susceptible de ser "
     "portado a otro sistema (PDF-imagen escaneado o entrega en papel)."),
    ("cobro_indebido", _cobro_indebido, "leve",
     "Cobrar por la primera copia, siendo que la entrega debe ser gratuita."),
    ("poder_notarial_exigido", _poder_notarial_exigido, "grave",
     "Exigir poder notarial cuando la ley admite expresamente el poder simple firmado por "
     "sistema electrónico que garantice su autenticidad."),
    ("sin_canal_publicado", _sin_canal_publicado, "leve",
     "No mantener publicado un canal digital operativo para recibir solicitudes de titulares."),
]


def fundamentos(supuesto_id: str, hoy: date) -> dict:
    """Devuelve a quién se reclama y con qué norma, según la fecha."""
    post = hoy >= VIGENCIA_21719

    base = {
        "formato_no_portable": {
            "norma_sectorial": "Ley 20.584, art. 13, inciso penúltimo (incorporado por la Ley 21.541): "
                               "la copia debe entregarse en formato estructurado, de uso común y lectura "
                               "legible, susceptible de ser portado a otro sistema.",
        },
        "poder_notarial_exigido": {
            "norma_sectorial": "Ley 20.584, art. 13 letra b: el poder simple puede otorgarse ante notario "
                               "O firmarse a través de un sistema electrónico que garantice su autenticidad, "
                               "conforme a la Ley 19.799. Exigir solo la vía notarial restringe un derecho "
                               "que la ley concede en términos alternativos.",
        },
        "cobro_indebido": {
            "norma_sectorial": "Ley 20.584, art. 13: la entrega es gratuita y sin dilaciones indebidas.",
        },
        "sin_respuesta_en_plazo": {
            "norma_sectorial": "Ley 20.584, art. 13: entrega sin dilaciones indebidas. Superintendencia de "
                               "Salud, Monografía N°7 (dic-2025): se sugiere un plazo no superior a 10 días hábiles.",
        },
        "sin_entrega": {
            "norma_sectorial": "Ley 20.584, art. 13: derecho del titular a obtener copia de su ficha clínica.",
        },
        "sin_canal_publicado": {
            "norma_sectorial": "—",
        },
    }[supuesto_id]

    if post:
        if supuesto_id == "cobro_indebido":
            # Calificarlo de grave es defendible —cobrar por lo gratuito obstaculiza el
            # acceso— pero no es evidente, así que se dice con ese matiz en vez de
            # afirmarlo. Un reclamo sobrecalificado se cae entero.
            base.update({
                "via": "Agencia de Protección de Datos Personales",
                "norma_datos": "Ley 21.719, art. 10: el derecho de acceso se ejerce en forma gratuita "
                               "al menos trimestralmente; solo procede cobrar costos directos cuando se "
                               "ejerce más de una vez en el trimestre.",
                "calificacion": "Infracción leve — art. 34 bis letra f). Se sostiene además, como "
                                "calificación alternativa, que el cobro improcedente obstaculiza el "
                                "ejercicio del derecho de acceso (infracción grave, art. 34 ter letra e).",
                "sancion": "Amonestación escrita o multa de hasta 5.000 UTM (art. 35 letra a); "
                           "hasta 10.000 UTM si se acoge la calificación de infracción grave.",
            })
        elif supuesto_id == "sin_canal_publicado":
            base.update({
                "via": "Agencia de Protección de Datos Personales",
                "norma_datos": "Ley 21.719, art. 14 ter letra c): el responsable debe mantener "
                               "permanentemente a disposición del público, en su sitio web o medio "
                               "equivalente, la dirección de correo, formulario de contacto o medio "
                               "tecnológico equivalente por el cual se le notifican las solicitudes "
                               "de los titulares.",
                "calificacion": "Infracción leve — art. 34 bis letras a) y b)",
                "sancion": "Amonestación escrita o multa de hasta 5.000 UTM (art. 35 letra a)",
            })
        else:
            base.update({
                "via": "Agencia de Protección de Datos Personales",
                "norma_datos": "Ley 21.719, art. 34 ter letra e): impedir u obstaculizar el ejercicio "
                               "legítimo del derecho de acceso o de portabilidad del titular.",
                "calificacion": "Infracción grave — art. 34 ter letra e)",
                "sancion": "Multa de hasta 10.000 UTM (art. 35 letra b). En caso de reincidencia, "
                           "hasta tres veces ese monto. La sanción se inscribe en el Registro Nacional "
                           "de Sanciones, público y gratuito (art. 39).",
            })
        base["procedimiento"] = ("Reclamación ante la Agencia conforme al art. 41 (tutela de derechos) "
                                 "y/o denuncia para el procedimiento sancionatorio del art. 42.")
    else:
        base.update({
            "via": "Superintendencia de Salud, y en paralelo juez civil (habeas data)",
            "norma_datos": "Ley 19.628, art. 16: si el responsable no se pronuncia sobre el requerimiento "
                           "de acceso dentro de dos días hábiles, se abre el amparo judicial.",
            "calificacion": "Reclamo ante la Superintendencia (Ley 20.584, arts. 37-38) y amparo del "
                            "art. 16 de la Ley 19.628",
            "sancion": "Instrucciones y fiscalización de la Superintendencia. En sede judicial, multa "
                       "de 1 a 50 UTM al responsable, en procedimiento sumario.",
            "procedimiento": "Reclamo al prestador, luego a la Superintendencia de Salud; amparo ante "
                             "juez civil del domicilio del titular.",
            "nota_temporal": f"⚠️ Desde el {VIGENCIA_21719.strftime('%d-%m-%Y')} esta misma conducta pasa "
                             "a ser infracción grave sancionable con hasta 10.000 UTM por la Agencia de "
                             "Protección de Datos (Ley 21.719, arts. 34 ter e y 35 b).",
        })
    return base


def detectar(fila: dict, hoy: date) -> list[dict]:
    hallazgos = []
    for sid, cond, gravedad, descripcion in SUPUESTOS:
        try:
            if cond(fila):
                hallazgos.append({
                    "supuesto": sid,
                    "gravedad_interna": gravedad,
                    "descripcion": descripcion,
                    **fundamentos(sid, hoy),
                })
        except (TypeError, KeyError):
            continue
    return hallazgos


def escrito(centro: str, fila: dict, hallazgos: list[dict], hoy: date) -> str:
    ptos = []
    for i, h in enumerate(hallazgos, 1):
        ptos.append(
            f"{i}. {h['descripcion']}\n"
            f"   Fundamento sectorial: {h['norma_sectorial']}\n"
            f"   Fundamento de protección de datos: {h['norma_datos']}\n"
            f"   Calificación: {h['calificacion']}\n"
            f"   Sanción aplicable: {h['sancion']}\n"
        )

    via = hallazgos[0]["via"]
    hechos = (
        f"   - Canal por el que se presentó la solicitud: {fila.get('canal_solicitud') or 'no publicado'}\n"
        f"   - Días hábiles hasta la primera respuesta: {fila.get('dias_habiles_primera_respuesta', 'sin respuesta')}\n"
        f"   - Días hábiles hasta la entrega: {fila.get('dias_habiles_entrega', 'sin entrega')}\n"
        f"   - Formato en que se entregó: {fila.get('formato_entrega', 'no entregó')}\n"
        f"   - Años de historial entregados: {fila.get('anios_historial_entregados', 'no aplica')}\n"
        f"   - ¿Cobró la primera copia?: {'Sí' if fila.get('cobro') else 'No'}\n"
        f"   - Requisitos adicionales exigidos: "
        f"{', '.join(fila.get('requisitos_adicionales', [])) or 'ninguno'}\n"
    )

    return f"""RECLAMO POR OBSTACULIZACIÓN DEL DERECHO DE ACCESO A LA FICHA CLÍNICA

Dirigido a: {via}
Prestador reclamado: {centro}
Fecha: {hoy.strftime('%d-%m-%Y')}

I. ANTECEDENTES DE HECHO

El titular solicitó al prestador individualizado copia íntegra de su ficha
clínica, al amparo del artículo 13 de la Ley N° 20.584. El comportamiento
registrado del prestador fue el siguiente:

{hechos}
II. INFRACCIONES QUE SE DENUNCIAN

{chr(10).join(ptos)}
III. PETICIÓN

Se solicita tener por presentado este reclamo, admitirlo a tramitación,
requerir al prestador la entrega de la información en el formato que la ley
exige, y aplicar las sanciones que en derecho correspondan.

---
[BORRADOR GENERADO AUTOMÁTICAMENTE — requiere la aprobación expresa del titular
antes de ser presentado. Los datos identificatorios del titular se completan al
momento de la presentación y no se almacenan en este sistema.]
"""


def main():
    ap = argparse.ArgumentParser(description="L16 — detecta incumplimientos y arma el reclamo")
    ap.add_argument("--registro", default=str(AQUI.parent / "registro" / "protocolos-aprendidos.jsonl"))
    ap.add_argument("--centro", default=None, help="Filtra por un centro")
    ap.add_argument("--emitir", action="store_true", help="Escribe los borradores a disco")
    ap.add_argument("--fecha", default=None, help="YYYY-MM-DD para simular la ruta post 1-dic-2026")
    args = ap.parse_args()

    hoy = date.fromisoformat(args.fecha) if args.fecha else date.today()
    ruta = Path(args.registro)
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Corre borrar_caso.py primero: el registro se llena ahí.")

    filas = [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.centro:
        filas = [f for f in filas if args.centro.lower() in f["centro"].lower()]

    regimen = "Ley 21.719 (Agencia)" if hoy >= VIGENCIA_21719 else "Ley 19.628 + Superintendencia"
    print(f"Régimen aplicable al {hoy}: {regimen}\n")

    total = 0
    for f in filas:
        h = detectar(f, hoy)
        if not h:
            print(f"[ok]   {f['centro']}: sin hallazgos.")
            continue
        total += len(h)
        graves = sum(1 for x in h if "grave" in x["calificacion"].lower())
        print(f"[!]    {f['centro']}: {len(h)} hallazgo(s), {graves} calificable(s) como grave")
        for x in h:
            print(f"         - {x['supuesto']}: {x['sancion'].split('. ')[0].rstrip('.')}")
        if args.emitir:
            salida = AQUI / f"reclamo-{f['centro'].lower().replace(' ', '-')}.txt"
            salida.write_text(escrito(f["centro"], f, h, hoy), encoding="utf-8")
            print(f"         -> {salida.name}")

    print(f"\n{total} hallazgo(s) en {len(filas)} prestador(es).")
    if not args.emitir:
        print("Agrega --emitir para escribir los borradores.")


if __name__ == "__main__":
    main()
