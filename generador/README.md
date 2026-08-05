# Generador de cohorte clínica sintética

Dos scripts, sin dependencias externas (solo stdlib de Python).

## 1. `generar_cohorte.py` — genera la población de pacientes

```
python generar_cohorte.py --n 200 --seed 42 --out cohorte.json
python generar_cohorte.py --n 200 --seed 42 --verificar          # además imprime tabla de verificación
```

Argumentos:
- `--n`: cantidad de pacientes (default 200)
- `--seed`: semilla del RNG, para reproducibilidad (default 42)
- `--out`: archivo JSON de salida (default `cohorte.json`)
- `--verificar`: imprime una tabla comparando la distribución obtenida vs. la esperada (útil para la demo)

Cada paciente tiene: `paciente_ref` (PAC-XXXX), `sexo`, `edad`, `tramo_fonasa`,
`especialidad_quirurgica`, `servicio_salud`, `dias_espera`, `fecha_ingreso_lista`.

### Qué constante tocar para cambiar cada cosa

Todo vive en el diccionario `SEMILLAS` al inicio del archivo:

| Para cambiar... | Tocar... |
|---|---|
| Proporción de sexo | `SEMILLAS["sexo"]` |
| Proporción por tramo de edad | `SEMILLAS["tramo_edad"]` |
| Proporción por tramo FONASA | `SEMILLAS["tramo_fonasa"]` |
| Proporción por especialidad quirúrgica | `SEMILLAS["especialidad"]` |
| Servicios de salud y su mediana de espera asociada | `SEMILLAS["servicios_salud"]` |
| Mediana nacional de días de espera (ancla de la lognormal) | `SEMILLAS["mediana_espera_iq"]` |
| Forma de la cola de `dias_espera` (dispersión) | constante `SIGMA_ESPERA` |
| Rango plausible de `dias_espera` | `MIN_DIAS_ESPERA` / `MAX_DIAS_ESPERA` |

Cada clave del diccionario `SEMILLAS` cita su origen en `semillas/semillas-publicas.md`
(sección §). El supuesto sobre la **forma** de la distribución de `dias_espera`
(lognormal, porque la fuente publica solo la mediana) está documentado en el
bloque de comentarios "SUPUESTO SOBRE LA FORMA DE dias_espera" del archivo.

## 2. `generar_ficha_pdf.py` — genera un informe de laboratorio HTML por paciente

```
python generar_ficha_pdf.py --paciente cohorte.json --index 0 --centro centro_a --out ficha_a.html
python generar_ficha_pdf.py --paciente cohorte.json --index 0 --centro centro_b --out ficha_b.html
python generar_ficha_pdf.py --paciente cohorte.json --index 0 --centro centro_c --out ficha_c.html
```

Argumentos:
- `--paciente`: archivo JSON de cohorte (generado por `generar_cohorte.py`)
- `--index`: índice del paciente dentro de la cohorte (default 0)
- `--centro`: `centro_a` | `centro_b` | `centro_c` — define qué vocabulario de analitos usa el informe
- `--out`: archivo HTML de salida

El HTML resultante se ve como un informe de laboratorio chileno real (encabezado
del centro, datos del paciente por seudónimo PAC-XXXX, tabla de analitos con
valor / unidad / rango de referencia). Se puede imprimir a PDF con Ctrl+P →
"Guardar como PDF" desde cualquier navegador.

**El punto clave**: los tres centros nombran el mismo analito distinto
(ej. "Glicemia en ayunas" / "Glucosa basal" / "GLUCOSA (ayuno)"), con
unidades y formato de rango de referencia también distintos. Esto es lo que
después se usa para demostrar la normalización de datos clínicos heterogéneos
entre centros — el problema real que "un wiki de salud" intenta resolver.

### Qué constante tocar para cambiar cada cosa

| Para cambiar... | Tocar... |
|---|---|
| Nombre/dirección de un centro | `VOCABULARIOS["centro_x"]["nombre_centro"]` / `["direccion"]` |
| Cómo un centro nombra un analito, su unidad o rango de referencia | `VOCABULARIOS["centro_x"]["analitos"]["<analito>"]` |
| Agregar un centro nuevo | copiar un bloque `"centro_x": {...}` dentro de `VOCABULARIOS`, con los mismos 5 analitos como claves |
| Rango de valores plausibles generados por analito | `RANGOS_VALOR_PLAUSIBLE` |

## Nota sobre PII

Todos los datos son sintéticos. `paciente_ref` es un seudónimo (PAC-XXXX), nunca
un nombre real. Cada ficha lleva una marca visible "DATO SINTÉTICO" al pie.
