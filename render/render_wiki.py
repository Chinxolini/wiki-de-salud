"""
render_wiki.py — genera el HTML autocontenido del "wiki de salud" a partir
de una lista de registros que cumplen schemas/wiki-salud.schema.json.

Solo stdlib. Sin dependencias externas, sin CDN, sin fetch.

Uso:
    python render_wiki.py --in wiki.json --out wiki-salud.html
"""

import argparse
import html
import json
from datetime import datetime, timezone


def _esc(valor):
    """Escapa a texto seguro para HTML. None -> cadena vacía."""
    if valor is None:
        return ""
    return html.escape(str(valor))


def _fmt_valor(valor, unidad):
    """Formatea valor + unidad para mostrar en pantalla."""
    if valor is None:
        texto = "—"
    else:
        texto = str(valor)
    if unidad:
        texto = f"{texto} {unidad}"
    return texto


def _marca_confianza(confianza):
    """Devuelve el span de la marca de confianza (punto ámbar/rojo) o nada si es alta."""
    if confianza == "media":
        return '<span class="marca marca-media" title="Confianza media">●</span>'
    if confianza == "baja":
        return '<span class="marca marca-baja" title="Confianza baja — lectura incierta, verificar contra el documento original">●</span>'
    return ""


def _consolidar_analitos(registros):
    """
    Agrupa todas las mediciones de todos los registros/exámenes por nombre_canonico.
    Devuelve dict: nombre_canonico -> lista de mediciones (con fecha, centro, etc.)
    ordenada por fecha descendente (las sin fecha al final).
    """
    consolidado = {}
    for reg in registros:
        centro = reg.get("centro_origen", "")
        for ex in reg.get("examenes", []):
            fecha = ex.get("fecha")
            for an in ex.get("analitos", []):
                nombre_can = an.get("nombre_canonico", "")
                consolidado.setdefault(nombre_can, []).append({
                    "fecha": fecha,
                    "centro": centro,
                    "nombre_original": an.get("nombre_original", ""),
                    "valor": an.get("valor"),
                    "unidad": an.get("unidad"),
                    "valor_canonico": an.get("valor_canonico"),
                    "unidad_canonica": an.get("unidad_canonica"),
                    "rango_referencia": an.get("rango_referencia"),
                    "fuera_de_rango": an.get("fuera_de_rango"),
                    "confianza": an.get("confianza", "alta"),
                })

    def clave_orden(m):
        # Fechas descendente; sin fecha va al final.
        return (m["fecha"] is None, m["fecha"] or "")

    for nombre_can, mediciones in consolidado.items():
        mediciones.sort(key=clave_orden)
        # Invertimos para que la más reciente quede primero, dejando las sin fecha al final.
        con_fecha = [m for m in mediciones if m["fecha"] is not None]
        sin_fecha = [m for m in mediciones if m["fecha"] is None]
        con_fecha.sort(key=lambda m: m["fecha"], reverse=True)
        consolidado[nombre_can] = con_fecha + sin_fecha

    return consolidado


def _linea_de_tiempo(registros):
    """
    Construye la lista de eventos (fecha, centro, tipo_examen, analitos) para
    la línea de tiempo, separando los que tienen fecha de los que no.
    """
    con_fecha = []
    sin_fecha = []
    for reg in registros:
        centro = reg.get("centro_origen", "")
        for ex in reg.get("examenes", []):
            evento = {
                "fecha": ex.get("fecha"),
                "centro": centro,
                "tipo_examen": ex.get("tipo_examen", ""),
                "analitos": ex.get("analitos", []),
            }
            if evento["fecha"] is None:
                sin_fecha.append(evento)
            else:
                con_fecha.append(evento)
    con_fecha.sort(key=lambda e: e["fecha"], reverse=True)
    return con_fecha, sin_fecha


def _tabla_analitos_evento(analitos):
    """Genera las filas de analitos dentro de un evento de la línea de tiempo."""
    filas = []
    for an in analitos:
        marca = _marca_confianza(an.get("confianza", "alta"))
        fuera = an.get("fuera_de_rango")
        clase_fuera = ' class="fuera-de-rango"' if fuera else ""
        valor_txt = _fmt_valor(an.get("valor"), an.get("unidad"))
        rango = an.get("rango_referencia")
        rango_txt = f' <span class="rango">(ref: {_esc(rango)})</span>' if rango else ""
        original = _esc(an.get("nombre_original", ""))
        canonico = _esc(an.get("nombre_canonico", ""))
        filas.append(
            f'<li{clase_fuera}>'
            f'<span class="analito-nombre" title="Nombre original en el documento: {original}">{canonico}</span>: '
            f'<span class="analito-valor">{_esc(valor_txt)}</span>{rango_txt} {marca}'
            f'</li>'
        )
    return "\n".join(filas)


def render_wiki(registros: list, sintetico: bool = False) -> str:
    """
    Genera el HTML autocontenido del wiki de salud a partir de una lista de
    registros que cumplen el schema wiki_salud (ver schemas/wiki-salud.schema.json).

    `sintetico`: si es True, agrega al pie la leyenda "DATOS SINTÉTICOS — demostración".
    El schema no trae un campo para esto, así que se indica explícitamente al llamar
    la función (o vía el flag --sintetico de la CLI) en vez de adivinarlo del contenido.
    """
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pacientes = {r.get("paciente_ref", "") for r in registros}
    paciente_ref = next(iter(pacientes)) if len(pacientes) == 1 else " / ".join(sorted(p for p in pacientes if p))

    centros = sorted({r.get("centro_origen", "") for r in registros if r.get("centro_origen")})
    n_examenes = sum(len(r.get("examenes", [])) for r in registros)

    hay_fallo = any(r.get("extraccion_fallida") for r in registros)

    # --- franja de aviso por extracción fallida ---
    aviso_fallo_html = ""
    if hay_fallo:
        docs_fallidos = [
            f'{_esc(r.get("centro_origen", ""))} ({_esc(r.get("documento_ref", ""))})'
            for r in registros if r.get("extraccion_fallida")
        ]
        aviso_fallo_html = (
            '<div class="aviso-fallo">'
            '⚠️ La extracción falló para uno o más documentos — la información de estos centros puede '
            'estar incompleta: ' + ", ".join(docs_fallidos) + '.'
            '</div>'
        )

    # --- cabecera ---
    cabecera_html = f"""
    <header>
      <h1>Wiki de salud</h1>
      <div class="cabecera-datos">
        <div><span class="etiqueta">Paciente</span><span class="valor-grande">{_esc(paciente_ref)}</span></div>
        <div><span class="etiqueta">Generado</span><span class="valor-grande">{_esc(ahora)}</span></div>
        <div><span class="etiqueta">Centros consolidados</span><span class="valor-grande">{len(centros)}</span></div>
        <div><span class="etiqueta">Exámenes consolidados</span><span class="valor-grande">{n_examenes}</span></div>
      </div>
      <div class="lista-centros">{_esc(", ".join(centros)) if centros else "—"}</div>
    </header>
    """

    # --- línea de tiempo ---
    con_fecha, sin_fecha = _linea_de_tiempo(registros)

    def _bloque_evento(ev):
        fecha_txt = ev["fecha"] if ev["fecha"] else "Sin fecha"
        return f"""
        <li class="evento">
          <div class="evento-cabecera">
            <span class="evento-fecha">{_esc(fecha_txt)}</span>
            <span class="evento-tipo">{_esc(ev["tipo_examen"])}</span>
            <span class="evento-centro">{_esc(ev["centro"])}</span>
          </div>
          <ul class="evento-analitos">
            {_tabla_analitos_evento(ev["analitos"])}
          </ul>
        </li>
        """

    timeline_con_fecha = "\n".join(_bloque_evento(e) for e in con_fecha) or "<li class='vacio'>Sin exámenes con fecha.</li>"
    timeline_sin_fecha_html = ""
    if sin_fecha:
        bloques = "\n".join(_bloque_evento(e) for e in sin_fecha)
        timeline_sin_fecha_html = f"""
        <h3>Sin fecha en el documento</h3>
        <ul class="timeline">
          {bloques}
        </ul>
        """

    timeline_html = f"""
    <section>
      <h2>Línea de tiempo de exámenes</h2>
      <ul class="timeline">
        {timeline_con_fecha}
      </ul>
      {timeline_sin_fecha_html}
    </section>
    """

    # --- tabla consolidada por analito ---
    consolidado = _consolidar_analitos(registros)

    def _fila_analito(nombre_can, mediciones):
        celdas = []
        for m in mediciones:
            marca = _marca_confianza(m["confianza"])
            fuera = m["fuera_de_rango"]
            clase_fuera = " fuera-de-rango" if fuera else ""
            fecha_txt = m["fecha"] if m["fecha"] else "s/f"
            original = _esc(m["nombre_original"])
            valor_orig_txt = _fmt_valor(m["valor"], m["unidad"])
            rango = m["rango_referencia"]
            rango_txt = f'<div class="rango">ref: {_esc(rango)}</div>' if rango else ""

            valor_can = m["valor_canonico"]
            unidad_can = m["unidad_canonica"]
            if valor_can is not None:
                # Valor comparable disponible: es el principal; el original queda en la traza.
                valor_can_txt = _fmt_valor(valor_can, unidad_can)
                bloque_principal = f'<div class="medicion-valor" title="Nombre original: {original}">{_esc(valor_can_txt)} {marca}</div>'
                bloque_traza = f'<div class="medicion-original">{original}: {_esc(valor_orig_txt)} · {_esc(m["centro"])}</div>'
            else:
                # Sin conversión posible: se muestra el valor original tal cual, sin inventar nada.
                bloque_principal = (
                    f'<div class="medicion-valor" title="Nombre original: {original}">{_esc(valor_orig_txt)} {marca}</div>'
                    f'<div class="sin-unidad-comun">sin unidad común</div>'
                )
                bloque_traza = f'<div class="medicion-original">{original} · {_esc(m["centro"])}</div>'

            celdas.append(f"""
            <td class="celda-medicion{clase_fuera}">
              <div class="medicion-fecha">{_esc(fecha_txt)}</div>
              {bloque_principal}
              {bloque_traza}
              {rango_txt}
            </td>
            """)
        return f"""
        <tr>
          <th class="col-analito">{_esc(nombre_can)}</th>
          {"".join(celdas)}
        </tr>
        """

    # Ordenamos las filas alfabéticamente por nombre canónico.
    nombres_ordenados = sorted(consolidado.keys(), key=lambda s: s.lower())
    max_columnas = max((len(consolidado[n]) for n in nombres_ordenados), default=0)

    filas_html = "\n".join(_fila_analito(n, consolidado[n]) for n in nombres_ordenados)

    tabla_html = f"""
    <section>
      <h2>Tabla consolidada por analito <span class="subtitulo-unidad">— valores en unidad canónica (comparables entre centros)</span></h2>
      <p class="nota-tabla">
        Cada fila es un analito normalizado (<code>nombre_canonico</code>). Las columnas muestran su
        evolución en el tiempo, más reciente primero. El valor destacado está convertido a la
        <strong>unidad canónica</strong> del analito para que sea comparable entre centros; el valor tal
        como aparece en el documento original (<code>nombre_original</code>, valor y unidad originales)
        figura en letra chica debajo, junto con el centro de origen. Cuando no fue posible convertir el
        valor, se muestra el original y se marca "sin unidad común".
      </p>
      <div class="tabla-scroll">
        <table class="tabla-consolidada">
          <tbody>
            {filas_html if filas_html else '<tr><td>Sin analitos registrados.</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>
    """ if max_columnas else """
    <section>
      <h2>Tabla consolidada por analito</h2>
      <p class="nota-tabla">Sin analitos registrados.</p>
    </section>
    """

    # --- leyenda de confianza ---
    leyenda_html = """
    <section class="leyenda">
      <h2>Marcas de confianza</h2>
      <ul>
        <li><span class="marca marca-alta">·</span> Confianza <strong>alta</strong> — sin marca.</li>
        <li><span class="marca marca-media">●</span> Confianza <strong>media</strong>.</li>
        <li><span class="marca marca-baja">●</span> Confianza <strong>baja</strong> — lectura incierta, verificar contra el documento original.</li>
      </ul>
    </section>
    """

    # --- notas de extracción por documento ---
    notas = [
        (r.get("centro_origen", ""), r.get("documento_ref", ""), r.get("notas_extraccion", ""))
        for r in registros if r.get("notas_extraccion")
    ]
    notas_html = ""
    if notas:
        filas_notas = "\n".join(
            f'<li><strong>{_esc(centro)}</strong> ({_esc(doc)}): {_esc(nota)}</li>'
            for centro, doc, nota in notas
        )
        notas_html = f"""
        <section>
          <h2>Notas de extracción</h2>
          <ul>{filas_notas}</ul>
        </section>
        """

    pie_sintetico = '<div class="pie-sintetico">DATOS SINTÉTICOS — demostración</div>' if sintetico else ""

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wiki de salud — {_esc(paciente_ref)}</title>
<style>
{_css()}
</style>
</head>
<body>
<div class="contenedor">
  {aviso_fallo_html}
  {cabecera_html}
  {timeline_html}
  {tabla_html}
  {leyenda_html}
  {notas_html}
</div>
<footer class="pie-fijo">
  <div>Documento generado a partir de los antecedentes entregados por los propios centros. No constituye diagnóstico ni indicación médica.</div>
  {pie_sintetico}
</footer>
</body>
</html>
"""


def _css() -> str:
    """CSS inline, sobrio, legible, imprimible, claro/oscuro."""
    return """
    :root {
      --fondo: #ffffff;
      --texto: #1a1a1a;
      --texto-suave: #555555;
      --borde: #dddddd;
      --fondo-header: #f7f7f7;
      --acento: #2b5c8a;
      --ambar: #c8860a;
      --rojo: #b3261e;
      --fondo-fuera: #fdecea;
      --fondo-aviso: #fff4e5;
      --borde-aviso: #e0a11a;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --fondo: #14171a;
        --texto: #e8e8e8;
        --texto-suave: #a0a0a0;
        --borde: #33383d;
        --fondo-header: #1c2024;
        --acento: #6fa8dc;
        --ambar: #e0a839;
        --rojo: #e57373;
        --fondo-fuera: #3a1f1e;
        --fondo-aviso: #3a2f14;
        --borde-aviso: #a37a1f;
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--fondo);
      color: var(--texto);
      line-height: 1.45;
    }
    .contenedor { max-width: 960px; margin: 0 auto; padding: 1.5rem 1rem 6rem; }
    h1 { font-size: 1.6rem; margin: 0 0 0.5rem; }
    h2 { font-size: 1.15rem; border-bottom: 1px solid var(--borde); padding-bottom: 0.3rem; margin-top: 2rem; }
    h3 { font-size: 1rem; color: var(--texto-suave); margin-top: 1.5rem; }
    code { background: var(--fondo-header); padding: 0.1rem 0.3rem; border-radius: 3px; }

    .aviso-fallo {
      background: var(--fondo-aviso);
      border: 1px solid var(--borde-aviso);
      border-radius: 6px;
      padding: 0.75rem 1rem;
      margin-bottom: 1rem;
      font-weight: 600;
    }

    header {
      background: var(--fondo-header);
      border: 1px solid var(--borde);
      border-radius: 8px;
      padding: 1rem 1.25rem;
      margin-bottom: 1rem;
    }
    .cabecera-datos {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 0.75rem;
      margin-top: 0.5rem;
    }
    .etiqueta { display: block; font-size: 0.75rem; color: var(--texto-suave); text-transform: uppercase; letter-spacing: 0.03em; }
    .valor-grande { display: block; font-size: 1.1rem; font-weight: 600; }
    .lista-centros { margin-top: 0.75rem; font-size: 0.85rem; color: var(--texto-suave); }

    ul.timeline { list-style: none; margin: 0; padding: 0; }
    li.evento {
      border: 1px solid var(--borde);
      border-radius: 6px;
      padding: 0.6rem 0.9rem;
      margin-bottom: 0.6rem;
    }
    li.vacio { color: var(--texto-suave); font-style: italic; border: none; }
    .evento-cabecera { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: baseline; margin-bottom: 0.4rem; }
    .evento-fecha { font-weight: 700; color: var(--acento); }
    .evento-tipo { font-weight: 600; }
    .evento-centro { font-size: 0.85rem; color: var(--texto-suave); }
    .evento-analitos { list-style: none; margin: 0; padding-left: 0.2rem; }
    .evento-analitos li { padding: 0.15rem 0; border-bottom: 1px dashed var(--borde); }
    .evento-analitos li:last-child { border-bottom: none; }
    .evento-analitos li.fuera-de-rango { background: var(--fondo-fuera); padding-left: 0.3rem; border-radius: 3px; }
    .analito-nombre { cursor: help; border-bottom: 1px dotted var(--texto-suave); }
    .analito-valor { font-weight: 600; }
    .rango { font-size: 0.8rem; color: var(--texto-suave); }

    .nota-tabla { font-size: 0.85rem; color: var(--texto-suave); }
    .tabla-scroll { overflow-x: auto; }
    table.tabla-consolidada { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
    table.tabla-consolidada th, table.tabla-consolidada td { border: 1px solid var(--borde); padding: 0.4rem 0.5rem; text-align: left; vertical-align: top; }
    th.col-analito { position: sticky; left: 0; background: var(--fondo-header); font-weight: 700; white-space: nowrap; }
    td.celda-medicion { min-width: 150px; }
    td.celda-medicion.fuera-de-rango { background: var(--fondo-fuera); }
    .medicion-fecha { font-size: 0.75rem; color: var(--texto-suave); }
    .medicion-valor { font-weight: 600; }
    .medicion-original { font-size: 0.72rem; color: var(--texto-suave); font-style: italic; }
    .medicion-centro { font-size: 0.72rem; color: var(--texto-suave); }
    .sin-unidad-comun { font-size: 0.7rem; color: var(--ambar); font-weight: 600; }
    .subtitulo-unidad { font-size: 0.8rem; font-weight: 400; color: var(--texto-suave); }

    .marca { font-weight: 900; }
    .marca-media { color: var(--ambar); }
    .marca-baja { color: var(--rojo); }
    .marca-alta { color: var(--texto-suave); }

    section.leyenda ul { list-style: none; padding: 0; }
    section.leyenda li { margin-bottom: 0.3rem; }

    .pie-fijo {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: var(--fondo-header);
      border-top: 1px solid var(--borde);
      padding: 0.6rem 1rem;
      font-size: 0.75rem;
      color: var(--texto-suave);
      text-align: center;
    }
    .pie-sintetico { font-weight: 700; color: var(--rojo); margin-top: 0.2rem; }

    @media print {
      .pie-fijo { position: static; margin-top: 2rem; }
      .contenedor { padding-bottom: 1rem; }
    }
    """


def main():
    """CLI: lee un JSON con lista de registros y escribe el HTML renderizado."""
    parser = argparse.ArgumentParser(description="Renderiza el wiki de salud a HTML autocontenido.")
    parser.add_argument("--in", dest="entrada", required=True, help="Ruta al JSON de entrada (lista de registros).")
    parser.add_argument("--out", dest="salida", required=True, help="Ruta del HTML de salida.")
    parser.add_argument("--sintetico", action="store_true", help="Marca el HTML como datos sintéticos de demostración.")
    args = parser.parse_args()

    with open(args.entrada, "r", encoding="utf-8") as f:
        registros = json.load(f)

    if isinstance(registros, dict):
        registros = [registros]

    html_final = render_wiki(registros, sintetico=args.sintetico)

    with open(args.salida, "w", encoding="utf-8") as f:
        f.write(html_final)

    print(f"OK: {args.salida} generado a partir de {len(registros)} registro(s).")


if __name__ == "__main__":
    main()
