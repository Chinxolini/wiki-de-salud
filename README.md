# Wiki de salud — MVP

Claude Impact Lab · Longevidad 2026 · Equipo LOS INMORTALES

Gestiona la solicitud del historial clínico propio, normaliza lo que devuelve cada
centro y lo entrega como un expediente portable del titular.

**Los datos viven en el dispositivo del usuario. Somos el cartero, no el archivo.**

## Piezas

Ver `LEGOS.md`. Cada pieza se cambia sin tocar las otras; el contrato central es
`schemas/wiki-salud.schema.json`.

## El viaje completo

| # | Paso | Pieza |
|---|---|---|
| 1 | La persona llega, dice dónde se atendió y firma el poder | `entrada/index.html` (L12) + `legal/` (L13) |
| 2 | Se resuelve por qué canal recibe cada prestador | `prestadores/` (L14) |
| 3 | Sale la solicitud (correo) o se prepara la acción asistida (formulario/mostrador) | L8 |
| 4 | El prestador responde a la casilla espejo; se lee y se extrae | `extraccion/extraer.py` |
| 5 | Se coteja contra el original y se escala lo dudoso | `extraccion/verificar.py` (L9) |
| 6 | Se consolida el wiki normalizado y se empaqueta con los originales | `render/` + `empaquetar.py` |
| 7 | Se borra todo y se emite la constancia | `borrar_caso.py` (L15) |

## Correr la demo

```bash
# 1. Cohorte sintética, sembrada con distribuciones oficiales (Glosa 06, 31-mar-2026)
python generador/generar_cohorte.py --n 3000 --seed 42 --out cohorte.json --verificar

# 2. La misma persona, tres centros que nombran los analitos distinto
python generador/generar_ficha_pdf.py

# 3. Extracción y normalización con Claude
export ANTHROPIC_API_KEY=...
python extraccion/extraer.py --entrada "demo/ficha-*.html" --salida demo/wiki.json

# 4. Cascada de verificación: coteja y escala lo dudoso
python extraccion/verificar.py --wiki demo/wiki.json --documentos "demo/ficha-*.html" \
    --salida demo/wiki-verificado.json

# 5. El wiki de salud
python render/render_wiki.py --in demo/wiki-verificado.json --out demo/wiki-salud.html

# 6. El cierre del arco: no queda nada del titular
python borrar_caso.py --caso CASO-0006 --motivo servicio_completado
```

La entrada del usuario se abre directo en el navegador: `entrada/index.html`.

## Límites del agente

- **Sí hace**: solicita el historial a los centros, lee lo que llega, normaliza
  nomenclaturas y unidades distintas al mismo campo, y arma un expediente portable.
- **No hace nunca**: no diagnostica, no indica tratamiento, no ajusta dosis, no
  completa un dato que no pueda leer.
- **Escala**: cuando la lectura de un documento no es confiable (discrepancia con
  el original, campos ilegibles, escaneo degradado, manuscrito), la extracción se
  reprocesa con un modelo mayor. Lo que ni así se resuelve queda marcado como
  ilegible en el expediente, visible y enlazado a su original.
- **No juzga suficiencia clínica.** Ese juicio no es del sistema. El médico
  tratante que recibe al titular verifica el dossier contra los documentos
  originales, que van incluidos en el paquete.
- **Borra.** Entregado el paquete, se suprimen la casilla, los documentos y los
  datos, y se emite constancia. Sobrevive solo el registro por prestador, sin PII.

## Datos

Todo el material de demostración es **sintético**. Las distribuciones (sexo, edad,
tramo FONASA, especialidad, tiempos de espera) reproducen las cifras oficiales
publicadas en la Glosa N°06, corte 31-mar-2026. Ver `semillas/semillas-publicas.md`,
con trazabilidad línea por línea a la fuente.
