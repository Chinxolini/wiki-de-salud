# Resultados — extracción sobre foto vs. HTML (OCR)

## Qué se probó

Si la extracción con Claude (`extraccion/extraer.py`, `claude-haiku-4-5`) sostiene la
calidad cuando el documento no es HTML limpio sino **una foto del papel** — que es lo
que manda de verdad un hospital público.

**Degradación** (`pruebas/fotografiar.py`): HTML → PDF limpio (Chrome headless) →
imagen (PyMuPDF 150 dpi) → perspectiva, rotación ±1,6°, iluminación despareja, blur
gaussiano, ruido de sensor y compresión JPEG calidad 60. Dureza **media**, seed 42.

**Corrida** (`--con-api`): 2 de los 6 casos del dataset (`CASO-0000`, `CASO-0001`),
5 documentos, 10 llamadas (HTML + foto por documento).

## Resultado

| Categoría | HTML | Foto |
|---|---|---|
| Diagnósticos | **10/10 (100%)** | **10/10 (100%)** |
| Medicamentos | **10/10 (100%)** | **10/10 (100%)** |
| Analitos | **25/25 (100%)** | **23/25 (92%)** |

Falsos positivos — HTML: 0 en las tres categorías. Foto: 2 analitos.

**Lo único que la foto perdió**: el valor de hemoglobina en un documento
(`centro_c` de `CASO-0000`). Diagnósticos y medicamentos no se resintieron.

Con 5 documentos no alcanza para una cifra estadística, y no se presenta como tal.
La señal que sí sostiene: **la degradación fotográfica media no colapsa la
extracción**; el costo se concentra en valores numéricos sueltos de laboratorio,
no en la estructura del documento.

## Por qué la primera medición dio 0%, 50% y 20%

Vale registrarlo porque es el hallazgo más útil de esta prueba, y no era el OCR.

Había **tres vocabularios canónicos distintos** conviviendo:

1. `api/extraer.js` (producción, la web) → texto legible: "Diabetes mellitus tipo 2",
   "Losartán", "Glucosa en ayunas".
2. `prompts/extraccion.md` (camino Python) → slugs: `diabetes_mellitus_tipo_2`,
   `glucosa_ayunas`.
3. `pruebas/generar_dataset.py` (la verdad de referencia) → **cómo lo escribe el
   centro_a**: "Glicemia en ayunas", "Losartán potásico", "Creatinina sérica".

Es exactamente el error que el vocabulario canónico existe para evitar: el canónico no
puede depender de cómo lo escriba un centro, porque entonces no converge con los otros.
Dos extracciones correctas contaban como error, y lo que es peor, **nada extraído por
el camino Python habría agrupado con lo extraído por la web**.

Se unificaron los tres al vocabulario de producción. Con la vara corregida, la
extracción que ya estaba bien pasó a medir 100%.

## Cómo reproducir

```
python pruebas/generar_dataset.py --seed 42 --n 6
python pruebas/fotografiar.py --dureza media
python pruebas/medir_ocr.py --dureza media --casos CASO-0000 CASO-0001
python pruebas/medir_ocr.py --con-api --dureza media --casos CASO-0000 CASO-0001 --salida pruebas/resultado_ocr_media.json
```

Sin `--con-api` no gasta tokens: solo informa qué haría.

## Qué falló en el camino

- Chrome headless da "Acceso denegado" con rutas relativas en `--print-to-pdf`;
  se resolvió con rutas absolutas y `--user-data-dir` propio.
- `evaluar.py` empareja por `(paciente_ref, documento_ref)`, y el `documento_ref` de
  una foto es `.jpg`, no `.html`; `medir_ocr.py` lo sobrescribe antes de comparar para
  comparar por contenido y no por nombre de archivo.
