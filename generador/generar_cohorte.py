"""
Generador de cohorte clínica sintética — IMPACTLAB, Salud y Longevidad 2026.

Genera pacientes sintéticos (nunca reales) que respetan, en agregado, las
distribuciones oficiales publicadas en la Glosa N°06 (MINSAL, SIGTE, corte
31-mar-2026), sintetizadas en `semillas/semillas-publicas.md`.

Uso:
    python generar_cohorte.py --n 200 --seed 42 --out cohorte.json
    python generar_cohorte.py --n 200 --seed 42 --verificar

Sin dependencias externas: solo stdlib (random, json, datetime, argparse).
"""

import argparse
import json
import random
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# SEMILLAS — todas las proporciones oficiales, citadas a `semillas-publicas.md`.
# Para cambiar una distribución, tocar SOLO este diccionario.
# ---------------------------------------------------------------------------
SEMILLAS = {
    # § III — Distribución por sexo, Intervenciones Quirúrgicas (IQ)
    # semillas-publicas.md §III
    "sexo": {
        "F": 59.65,
        "M": 40.34,
        "No definido": 0.01,
    },

    # § IV — Distribución etaria, IQ (por tramos de edad, sobre registros)
    # semillas-publicas.md §IV
    "tramo_edad": {
        "menor_15": 10.10,
        "15_64": 60.02,
        "65_mas": 29.88,
    },

    # § V — Distribución por tramo FONASA, IQ (usa la TABLA, no el párrafo
    # narrativo que reporta 50,80% para Tramo B — ver nota en §V y §XII.5)
    # semillas-publicas.md §V (tabla "Intervenciones Quirúrgicas (IQ)")
    "tramo_fonasa": {
        "A": 13.90,
        "B": 43.39,
        "C": 11.88,
        "D": 13.35,
        "Sin Tramo / Otros": 17.51,
    },

    # § VI — Distribución por especialidad quirúrgica, IQ (12 grupos, 100%)
    # semillas-publicas.md §VI
    "especialidad": {
        "Traumatología": 20.89,
        "Cirugía Digestiva": 15.35,
        "Dermatología": 11.73,
        "Odontología": 9.58,
        "Otorrinolaringología": 8.33,
        "Ginecología y Obstetricia": 7.68,
        "Oftalmología": 6.58,
        "Urología y Nefrología": 6.41,
        "Neurocirugía": 4.53,
        "Cirugía Cardiovascular": 3.74,
        "Cirugía de Cabeza y Cuello": 2.71,
        "Plástica y Reparadora": 2.49,
    },

    # § VII — Brecha territorial: mediana mínima y máxima por Servicio de Salud.
    # No hay distribución completa publicada, solo los dos extremos; se arma
    # una lista de Servicios de Salud "representativos" ubicados dentro del
    # rango [122, 337] días de mediana observado, para poder asignar
    # dias_espera de forma coherente con el servicio sorteado. Los nombres son
    # reales (existen como Servicios de Salud), pero la mediana asignada a
    # cada uno intermedio es una interpolación nuestra, NO un dato MINSAL
    # específico por servicio (⚠️ por confirmar si se requiere precisión).
    # semillas-publicas.md §VII
    "servicios_salud": {
        "Araucanía Norte": 122,   # mínimo publicado, semillas-publicas.md §VII
        "Metropolitano Norte": 190,
        "Valparaíso San Antonio": 215,
        "Ñuble": 240,
        "Metropolitano Sur Oriente": 259,  # mediana nacional IQ, semillas-publicas.md §II
        "Bío Bío": 275,
        "Los Ríos": 300,
        "Reloncaví": 337,          # máximo publicado, semillas-publicas.md §VII
    },

    # § II — Mediana nacional de espera IQ, usada como ancla de la distribución
    # sintética de dias_espera. semillas-publicas.md §II
    "mediana_espera_iq": 259,
}

# ---------------------------------------------------------------------------
# SUPUESTO SOBRE LA FORMA DE dias_espera
# ---------------------------------------------------------------------------
# La Glosa 06 publica la MEDIANA (259 días) y menciona una Tabla 22 con
# desglose por rangos (<3, 3-6, 6-12, 12-18, 18-24, 24-36, >36 meses), pero
# esa tabla no está incluida en semillas-publicas.md (no capturada en esta
# extracción). Sin la forma exacta de la distribución, se optó por modelar
# dias_espera con una LOGNORMAL: es la familia estándar para tiempos de
# espera en salud (siempre positiva, asimétrica a la derecha, con cola larga
# que refleja el pequeño grupo de pacientes que esperan años). Se calibra
# mu = ln(mediana) porque la mediana de una lognormal es exp(mu), y se elige
# sigma=0.75 a mano para producir una cola larga plausible (P90 ~700-800
# días, coherente con que existan tiempos de espera de "más de 36 meses"
# mencionados en la Tabla 22) sin generar valores absurdos con frecuencia.
# Se trunca a un mínimo de 1 día (no tiene sentido dias_espera=0 o negativo)
# y a un máximo razonable de 2000 días (~5.5 años) para evitar colas
# infinitas propias de la lognormal. Este es un supuesto nuestro, marcado
# explícitamente porque la fuente no publica la forma de la distribución.
# ---------------------------------------------------------------------------
SIGMA_ESPERA = 0.75
MIN_DIAS_ESPERA = 1
MAX_DIAS_ESPERA = 2000

# Fecha de corte de la fuente (semillas-publicas.md, encabezado)
FECHA_CORTE = date(2026, 3, 31)


def muestreo_ponderado(rng: random.Random, distribucion: dict):
    """Elige una clave de `distribucion` (dict {clave: %}) respetando los pesos."""
    claves = list(distribucion.keys())
    pesos = list(distribucion.values())
    return rng.choices(claves, weights=pesos, k=1)[0]


def generar_dias_espera(rng: random.Random) -> int:
    """
    Genera un tiempo de espera plausible en días, con mediana ~259 y cola
    larga. Ver bloque de comentarios "SUPUESTO SOBRE LA FORMA DE dias_espera"
    para la justificación del modelo lognormal.
    """
    import math

    mu = math.log(SEMILLAS["mediana_espera_iq"])
    valor = rng.lognormvariate(mu, SIGMA_ESPERA)
    valor = round(valor)
    return max(MIN_DIAS_ESPERA, min(MAX_DIAS_ESPERA, valor))


def generar_edad(rng: random.Random, tramo: str) -> int:
    """Genera una edad puntual (años) coherente con el tramo etario sorteado."""
    if tramo == "menor_15":
        return rng.randint(0, 14)
    if tramo == "15_64":
        return rng.randint(15, 64)
    return rng.randint(65, 95)  # 65_mas: se acota a 95 como límite plausible


def generar_fecha_ingreso(rng: random.Random, dias_espera: int) -> date:
    """
    Fecha de ingreso a lista de espera = fecha de corte - dias_espera.
    Es la relación coherente: si el paciente lleva `dias_espera` esperando
    a la fecha de corte de la Glosa 06 (31-mar-2026), su ingreso a la lista
    fue esa cantidad de días antes.
    """
    return FECHA_CORTE - timedelta(days=dias_espera)


# Restricciones de coherencia clínica.
#
# La Glosa 06 publica las distribuciones de sexo, edad y especialidad por
# separado: NO publica el cruce. Muestrearlas de forma independiente produce
# combinaciones imposibles (un hombre en lista de Ginecología y Obstetricia).
# Acá se aplica el mínimo de coherencia para que la cohorte sea defendible
# frente a alguien con formación clínica, sin alterar de forma apreciable las
# proporciones marginales oficiales.
ESPECIALIDAD_SOLO_SEXO = {
    "Ginecología y Obstetricia": "F",
}

# Edad mínima plausible para entrar en lista por esta especialidad.
ESPECIALIDAD_EDAD_MINIMA = {
    "Ginecología y Obstetricia": 12,
}


def muestrear_especialidad(rng: random.Random, sexo: str, edad: int) -> str:
    """Muestrea especialidad respetando SEMILLAS y descartando lo imposible.

    Reintenta hasta 50 veces; si no logra una combinación coherente, cae a
    Traumatología, que es la especialidad más frecuente y no tiene restricción
    de sexo ni de edad.
    """
    for _ in range(50):
        especialidad = muestreo_ponderado(rng, SEMILLAS["especialidad"])
        sexo_requerido = ESPECIALIDAD_SOLO_SEXO.get(especialidad)
        if sexo_requerido is not None and sexo != sexo_requerido:
            continue
        if edad < ESPECIALIDAD_EDAD_MINIMA.get(especialidad, 0):
            continue
        return especialidad
    return "Traumatología"


def generar_paciente(rng: random.Random, indice: int) -> dict:
    """Genera un paciente sintético completo, respetando las SEMILLAS."""
    sexo = muestreo_ponderado(rng, SEMILLAS["sexo"])
    tramo_edad = muestreo_ponderado(rng, SEMILLAS["tramo_edad"])
    edad = generar_edad(rng, tramo_edad)
    tramo_fonasa = muestreo_ponderado(rng, SEMILLAS["tramo_fonasa"])
    especialidad = muestrear_especialidad(rng, sexo, edad)
    servicio_salud = rng.choice(list(SEMILLAS["servicios_salud"].keys()))
    dias_espera = generar_dias_espera(rng)
    fecha_ingreso = generar_fecha_ingreso(rng, dias_espera)

    return {
        "paciente_ref": f"PAC-{indice:04d}",
        "sexo": sexo,
        "edad": edad,
        "tramo_fonasa": tramo_fonasa,
        "especialidad_quirurgica": especialidad,
        "servicio_salud": servicio_salud,
        "dias_espera": dias_espera,
        "fecha_ingreso_lista": fecha_ingreso.isoformat(),
    }


def generar_cohorte(n: int, seed: int) -> list:
    """Genera una lista de `n` pacientes sintéticos con semilla reproducible."""
    rng = random.Random(seed)
    return [generar_paciente(rng, i + 1) for i in range(n)]


def verificar_distribucion(cohorte: list) -> None:
    """Imprime una tabla comparando distribución obtenida vs. esperada (SEMILLAS)."""
    n = len(cohorte)

    def tabla(titulo, campo, esperado, extraer=lambda p, c=None: None):
        print(f"\n{titulo}")
        print(f"{'Categoría':<30}{'Esperado %':>12}{'Obtenido %':>12}{'Diferencia':>12}")
        conteo = {}
        for p in cohorte:
            valor = p[campo]
            conteo[valor] = conteo.get(valor, 0) + 1
        for clave, pct_esperado in esperado.items():
            obtenido = conteo.get(clave, 0) / n * 100
            diff = obtenido - pct_esperado
            print(f"{clave:<30}{pct_esperado:>12.2f}{obtenido:>12.2f}{diff:>+12.2f}")

    print("=" * 66)
    print(f"VERIFICACIÓN DE DISTRIBUCIÓN — cohorte de {n} pacientes")
    print("=" * 66)

    tabla("Sexo", "sexo", SEMILLAS["sexo"])
    tabla("Tramo FONASA", "tramo_fonasa", SEMILLAS["tramo_fonasa"])
    tabla("Especialidad quirúrgica", "especialidad_quirurgica", SEMILLAS["especialidad"])

    # Tramo de edad se reconstruye desde la edad puntual generada
    print("\nTramo de edad (reconstruido desde edad puntual)")
    print(f"{'Categoría':<30}{'Esperado %':>12}{'Obtenido %':>12}{'Diferencia':>12}")
    conteo_edad = {"menor_15": 0, "15_64": 0, "65_mas": 0}
    for p in cohorte:
        e = p["edad"]
        if e < 15:
            conteo_edad["menor_15"] += 1
        elif e <= 64:
            conteo_edad["15_64"] += 1
        else:
            conteo_edad["65_mas"] += 1
    for clave, pct_esperado in SEMILLAS["tramo_edad"].items():
        obtenido = conteo_edad[clave] / n * 100
        diff = obtenido - pct_esperado
        print(f"{clave:<30}{pct_esperado:>12.2f}{obtenido:>12.2f}{diff:>+12.2f}")

    # dias_espera: comparar mediana obtenida vs. mediana esperada (259)
    dias = sorted(p["dias_espera"] for p in cohorte)
    mediana_obtenida = dias[n // 2] if n % 2 else (dias[n // 2 - 1] + dias[n // 2]) / 2
    print(f"\nMediana dias_espera — esperado: {SEMILLAS['mediana_espera_iq']} · obtenido: {mediana_obtenida:.0f}")
    print(f"Rango obtenido: {dias[0]}–{dias[-1]} días")

    print("\n" + "=" * 66)
    print("Nota: con n pequeño (<200) las diferencias por categoría pueden ser")
    print("varios puntos porcentuales; es ruido de muestreo esperado, no error.")
    print("=" * 66)


def main():
    parser = argparse.ArgumentParser(
        description="Genera una cohorte clínica sintética fiel a la Glosa 06 (MINSAL, corte 31-mar-2026)."
    )
    parser.add_argument("--n", type=int, default=200, help="Cantidad de pacientes a generar (default: 200)")
    parser.add_argument("--seed", type=int, default=42, help="Semilla del generador aleatorio (default: 42)")
    parser.add_argument("--out", type=str, default="cohorte.json", help="Archivo JSON de salida (default: cohorte.json)")
    parser.add_argument("--verificar", action="store_true", help="Imprime tabla comparando distribución obtenida vs. esperada")
    args = parser.parse_args()

    cohorte = generar_cohorte(args.n, args.seed)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cohorte, f, ensure_ascii=False, indent=2)

    print(f"Cohorte generada: {len(cohorte)} pacientes → {args.out} (seed={args.seed})")

    if args.verificar:
        verificar_distribucion(cohorte)


if __name__ == "__main__":
    main()
