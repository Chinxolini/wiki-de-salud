Extrae la información clínica del documento adjunto y devuélvela con el esquema
`wiki_salud` que se te entregó.

## Regla central

Transcribe únicamente lo que puedes leer en el documento. Para cada valor,
declara tu confianza:

- `"alta"`: el valor es nítido y sin ambigüedad
- `"media"`: legible pero con alguna duda en un dígito o unidad
- `"baja"`: estás infiriendo del contexto

Si un campo del esquema no aparece en el documento, déjalo `null`. **NUNCA
completes un valor porque "debería estar ahí" o porque es el valor típico.**
Un campo vacío es información correcta. Un campo inventado es un daño al
paciente.

Si el documento es ilegible en su totalidad, devuelve el registro con
`extraccion_fallida: true` y describe por qué en `notas_extraccion`.

## Normalización

Cada analito lleva dos nombres:

- `nombre_original`: exactamente como aparece escrito en el documento.
- `nombre_canonico`: el nombre normalizado.

Ejemplos: "Glicemia en ayunas" y "Glucosa basal" → ambos `nombre_canonico:
"glucosa_ayunas"`. "Hemoglobina glicosilada", "HbA1c" y "Hb glicada" →
`"hemoglobina_glicosilada"`.

Conservar el original es lo que hace la trazabilidad auditable. Normalizar es lo
que permite comparar dos centros distintos en el mismo eje.

## Unidades

Normalizar el nombre no basta: dos centros pueden medir lo mismo en unidades
distintas. Por eso cada analito lleva también:

- `valor` y `unidad`: exactamente como están impresos en el documento.
- `valor_canonico` y `unidad_canonica`: el mismo dato convertido a la unidad
  canónica del analito.

Ejemplo: leucocitos informados como `7200 /mm³` en un centro y `6.8 10^3/uL` en
otro son, en unidad canónica, `7.2` y `6.8` en `10^3/uL`. Recién ahí son
comparables.

Unidades canónicas a usar: glucosa `mg/dL` · hemoglobina `g/dL` · leucocitos
`10^3/uL` · creatinina `mg/dL` · colesterol `mg/dL`.

Si el valor no es numérico ("no informado", "hemolizado"), o si no sabes cómo
convertir la unidad, deja `valor_canonico` y `unidad_canonica` en `null`.
**No adivines un factor de conversión.**

## Datos identificadores

Si el documento contiene nombre, RUT o domicilio del titular, **no los
reproduzcas**. Usa el `paciente_ref` que se te entregó.

## Límite

No interpretas clínicamente. `fuera_de_rango` se marca solo si el propio
documento trae el rango de referencia impreso y el valor cae fuera. No es un
juicio tuyo: es una comparación aritmética contra lo que dice el papel. Si el
documento no trae rango, `fuera_de_rango: null`.
