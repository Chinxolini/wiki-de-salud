# pruebas/ — dataset de testing con verdad de referencia

## Qué es

Un dataset sintético con **ground truth**: para cada caso, fichas HTML de 2 o 3
centros (mismo paciente, cada centro describiéndolo distinto) más un
`verdad.json` que dice exactamente qué debería devolver una extracción
perfecta según `schemas/wiki-salud.schema.json`.

Sin esto no se podía medir si `extraccion/extraer.py` acierta: se podían
generar fichas y extraer datos, pero no había con qué comparar el resultado.

Casos difíciles que el dataset incluye a propósito, en todos los casos:

- **Conversión de unidades** — leucocitos en `/mm³` (centro_a), `cél/mm³`
  (centro_b) y `10³/µL` (centro_c): mismo valor real, tres unidades.
- **Nombre comercial vs. principio activo** — "COZAAR 50 mg" / "Losartán
  potásico 50 mg" / "losartan potasico 50" deben converger en el mismo
  `principio_activo`.
- **Mismo analito, nombre distinto por centro** — "Glicemia en ayunas" /
  "Glucosa basal" / "GLUCOSA (ayuno)", heredado de los vocabularios de
  `generador/generar_ficha_pdf.py`.
- **Valores ilegibles** — al menos un caso trae un analito marcado como no
  legible en un centro, para ejercitar `campos_ilegibles`.

## Cómo se genera

```
python pruebas/generar_dataset.py --seed 42 --n 6
python pruebas/generar_dataset.py --seed 42 --n 6 --out otra/carpeta
```

`--seed` fija la reproducibilidad (mismo seed = mismo dataset byte a byte).
`--n` controla cuántos casos se generan. Salida por defecto:

```
pruebas/dataset/
  INDICE.json                          ← lista de casos
  CASO-0000/
    ficha-centro_a.html
    ficha-centro_c.html
    verdad.json
  CASO-0001/
    ...
```

El script **reutiliza, no reimplementa**, los vocabularios de analitos de
`generador/generar_ficha_pdf.py` (`VOCABULARIOS`) y el envoltorio HTML de
`generador/generar_ficha_completa.py` (`envoltura`, `BASE_CSS`). Los
vocabularios de diagnósticos y medicamentos sí son propios de `pruebas/`,
porque no existían antes en `generador/`.

Todos los pacientes son sintéticos: `paciente_ref` con formato `PAC-9XXX`
(rango reservado para no chocar con `generador/cohorte.json`).

## Cómo se evalúa

Dos modos, ninguno gasta tokens salvo que el usuario corra la extracción real
por su cuenta:

```
python pruebas/evaluar.py --dry-run
```

Valida que el dataset es internamente coherente, **sin llamar a la API**:
cada ficha HTML referenciada existe, cada `verdad.json` conforma al schema
`wiki-salud.schema.json` (required, enums, additionalProperties), los
diagnósticos y medicamentos canónicos convergen entre los centros de un mismo
caso, y todo analito con `valor: null` aparece también en `campos_ilegibles`.

```
python pruebas/evaluar.py --extraccion salida_extraccion.json
```

Compara una extracción real (la salida directa de `extraccion/extraer.py`,
una lista de registros `wiki_salud`) contra `verdad.json` de cada caso.
Empareja por `(paciente_ref, documento_ref)`.

## Qué mide cada métrica

- **Diagnósticos correctos** — de los diagnósticos esperados, cuántos aparecen
  en la extracción con el mismo `nombre_canonico` (comparación normalizada:
  minúsculas, sin espacios sobrantes).
- **Medicamentos correctos** — igual, pero sobre `principio_activo`: mide si
  el pipeline resolvió el nombre comercial al principio activo correcto.
- **Analitos correctos** — el `nombre_canonico` coincide y el `valor_canonico`
  cae dentro de una tolerancia de ±0.05 en la `unidad_canonica` esperada. Para
  el caso ilegible, se considera acierto si la extracción también devolvió
  `valor_canonico: null` (no inventó un número).
- **Falsos positivos** — entradas que la extracción devolvió y que no están en
  `verdad.json` (por categoría: diagnósticos, medicamentos, analitos).
- **Convergencia canónica entre centros** — de los casos con 2+ documentos,
  en cuántos los diagnósticos, medicamentos y el valor de leucocitos
  coinciden entre todos los centros extraídos. Es la métrica que más importa:
  el punto del producto es que información dicha distinto por cada centro
  termine siendo *el mismo dato* en el expediente unificado.

## Supuestos tomados

- No se usa la librería `jsonschema` (regla del proyecto: solo stdlib). El
  validador de `evaluar.py` cubre lo que `wiki-salud.schema.json` usa
  (`type`, `properties`, `required`, `additionalProperties`, `enum`, arrays),
  no es un validador JSON Schema genérico.
- El emparejamiento extracción↔verdad asume que quien corre `extraer.py`
  preserva `documento_ref` = nombre del archivo HTML (comportamiento por
  defecto de `extraccion/extraer.py`, que usa `ruta.name`) y pasa el
  `paciente_ref` correcto de cada caso.
- Los rangos de referencia canónicos (para `fuera_de_rango`) se tomaron de los
  del centro_a en `generador/`, por ser el más completo; no representan una
  fuente clínica oficial — son sintéticos, igual que el resto del dataset.
