# Wiki de salud — MVP

Claude Impact Lab · Longevidad 2026 · Equipo LOS INMORTALES

Gestiona la solicitud del historial clínico propio, normaliza lo que devuelve cada
centro y lo entrega como un expediente portable del titular.

**Los datos viven en el dispositivo del usuario. Somos el cartero, no el archivo.**

## Piezas

Ver `LEGOS.md`. Cada pieza se cambia sin tocar las otras; el contrato central es
`schemas/wiki-salud.schema.json`.

## Correr la demo

```bash
# 1. Cohorte sintética, sembrada con distribuciones oficiales (Glosa 06, 31-mar-2026)
python generador/generar_cohorte.py --n 3000 --seed 42 --out cohorte.json --verificar

# 2. La misma persona, tres centros que nombran los analitos distinto
python generador/generar_ficha_pdf.py

# 3. Extracción y normalización con Claude
export ANTHROPIC_API_KEY=...
python extraccion/extraer.py --entrada "demo/ficha-*.html" --salida demo/wiki.json

# 4. El wiki de salud
python render/render_wiki.py --in demo/wiki.json --out demo/wiki-salud.html
```

## Límites del agente

- **Sí hace**: solicita el historial a los centros, lee lo que llega, normaliza
  nomenclaturas y unidades distintas al mismo campo, y arma un expediente portable.
- **No hace nunca**: no diagnostica, no indica tratamiento, no ajusta dosis, no
  completa un dato que no pueda leer.
- **Deriva**: toda evaluación de suficiencia clínica va a una profesional de salud
  antes de responderle al centro.

## Datos

Todo el material de demostración es **sintético**. Las distribuciones (sexo, edad,
tramo FONASA, especialidad, tiempos de espera) reproducen las cifras oficiales
publicadas en la Glosa N°06, corte 31-mar-2026. Ver `semillas/semillas-publicas.md`,
con trazabilidad línea por línea a la fuente.
