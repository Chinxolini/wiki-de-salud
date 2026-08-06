# Resultados — extracción sobre foto vs. HTML (OCR)

## Qué se probó

Si la extracción con Claude (`extraccion/extraer.py`, `claude-haiku-4-5`) sostiene
la calidad cuando el documento no es HTML limpio sino una foto del papel —
que es lo que manda de verdad un hospital público.

**Pipeline de degradación** (`pruebas/fotografiar.py`): HTML → PDF limpio
(Chrome headless) → imagen (PyMuPDF, 150dpi) → degradación fotográfica
(perspectiva, rotación ±1.6°, iluminación despareja, blur gaussiano,
ruido de sensor, compresión JPEG calidad 60) → dureza **media**, seed 42.

**Corrida real** (gasta tokens, `--con-api`): 2 de los 6 casos del dataset
(`CASO-0000`, `CASO-0001`), 5 documentos, 10 llamadas totales (HTML + foto
por documento).

## Tabla HTML vs. foto

| Categoría     | HTML          | Foto          |
|---------------|---------------|---------------|
| Diagnósticos  | 0/10 (0.0%)   | 0/10 (0.0%)   |
| Medicamentos  | 5/10 (50.0%)  | 5/10 (50.0%)  |
| Analitos      | 5/25 (20.0%)  | 4/25 (16.0%)  |

Falsos positivos — HTML: dg=10 med=5 analitos=20. Foto: dg=10 med=5 analitos=21.

Campos donde la foto perdió información respecto del HTML propio (no
respecto de la verdad): **2 de 5 documentos** —

- `centro_c` / `ficha-centro_c.html`: perdió el diagnóstico de diabetes.
- `centro_c` / `ficha-centro_c.html`: perdió el valor de hemoglobina.

## Hallazgo honesto: los números absolutos son bajos por un motivo que NO es la foto

Los porcentajes contra `verdad.json` son bajos en **ambos** medios (HTML y
foto parejos en diagnósticos y medicamentos). La causa no es degradación
fotográfica: el modelo devuelve `nombre_canonico` como slug
(`diabetes_mellitus_tipo_2`, `losartan`, `glucosa_ayunas`) mientras
`verdad.json` espera texto legible (`"Diabetes Mellitus tipo 2"`,
`"Losartán potásico"`, `"Glicemia en ayunas"`). El comparador de
`evaluar.py` normaliza mayúsculas/espacios pero no reconcilia una
convención de nombres distinta de la otra, así que casi todo cuenta como
"no coincide" — incluso cuando el dato extraído es clínicamente correcto.

Esto es un desajuste entre `prompts/extraccion.md` y el vocabulario
canónico de `pruebas/generar_dataset.py`, preexistente y ortogonal al OCR.
No se tocó (fuera del alcance de esta prueba: no se modificó ningún prompt
ni el dataset). Por eso la lectura útil de esta prueba **no es el
porcentaje absoluto**, sino la comparación HTML-vs-foto bajo la misma vara:
ahí sí se aísla el efecto de la foto.

## Lectura de esa comparación

Con esa vara pareja, la foto perdió **1 punto porcentual en analitos**
(20.0% → 16.0%, es decir 4/25 vs 5/25 — una diferencia de un solo analito)
y **0 puntos en diagnósticos y medicamentos** sobre esta muestra de 2
casos / 5 documentos. Un documento (`centro_c` de `CASO-0000`) perdió un
diagnóstico y un valor de hemoglobina al pasar por la cámara; el resto de
los documentos no mostró diferencia detectable.

Con solo 5 documentos no alcanza para una conclusión estadística. La
señal que sí sostiene: la foto con degradación "media" (rotación leve,
blur, ruido, JPEG 60) no colapsó la extracción — el modelo sigue leyendo
la tabla y los valores en la inmensa mayoría de los campos.

## Qué falló en el camino

- Chrome headless fallaba con "Acceso denegado" al usar rutas relativas en
  `--print-to-pdf`; se resolvió con rutas absolutas + `--user-data-dir`
  propio (evita el lock del perfil real de Chrome).
- El comparador de `evaluar.py` empareja extracción↔verdad por
  `(paciente_ref, documento_ref)`, y `documento_ref` de una foto es
  `ficha-centro_a.jpg`, no `ficha-centro_a.html`. `medir_ocr.py` sobrescribe
  `documento_ref`/`paciente_ref` en el registro extraído con los valores
  conocidos del caso antes de comparar, para no comparar por nombre de
  archivo sino por contenido.
- El desajuste de canonicalización (arriba) no se arregló: no estaba en el
  alcance de esta tarea y tocarlo implica decidir si se corrige el prompt o
  el dataset de verdad — una decisión de producto, no de esta prueba.

## Cómo reproducir

```
python pruebas/fotografiar.py --dureza media
python pruebas/medir_ocr.py --dureza media --casos CASO-0000 CASO-0001        # dry-run, sin tokens
python pruebas/medir_ocr.py --con-api --dureza media --casos CASO-0000 CASO-0001 --salida pruebas/resultado_ocr_media.json
```
