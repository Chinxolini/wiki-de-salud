# Legos del MVP

Cada pieza se cambia sin tocar las otras. Si algo se discute con el equipo, se discute **una pieza**.

| # | Lego | Archivo | Contrato con el resto | Estado |
|---|---|---|---|---|
| L1 | **Semillas públicas** | `semillas/semillas-publicas.md` | Solo datos. Nadie depende de su formato, solo de sus números | ✅ |
| L2 | **Generador de cohorte** | `generador/generar_cohorte.py` | Entrada: L1 · Salida: `cohorte.json` | 🔨 |
| L3 | **Generador de fichas** | `generador/generar_ficha_pdf.py` | Entrada: un paciente de L2 · Salida: HTML/PDF por centro | 🔨 |
| L4 | **Prompt de extracción** | `prompts/extraccion.md` | Entrada: PDF de L3 · Salida: conforme a L5 | ✅ |
| L5 | **Schema wiki de salud** | `schemas/wiki-salud.schema.json` | **El contrato central.** Todo lo demás se acomoda a él | ✅ |
| L6 | **System prompt orquestador** | `prompts/orquestador.md` | Usa L7 | ✅ |
| L7 | **Tools schema** | `tools/schema.json` | 5 tools. Las implementaciones son intercambiables | ✅ |
| L8 | **Mail-service** | *(de Mauro)* | Implementa `buscar_correos`, `descargar_adjunto`, `enviar_correo` de L7 | ⬜ |
| L9 | **Panel de revisión humana** | *(pendiente)* | Consume `derivar_a_revision_humana` de L7 | ⬜ |
| L10 | **Render del wiki** | *(pendiente)* | Entrada: L5 · Salida: `wiki-salud.html` | ⬜ |

## Piezas bloqueadas (decisión de Ignacio, no se discuten hoy)

- **Carga manual de PDF** como camino de entrada — queda fuera. No afecta a ningún otro lego: si se
  reactiva, entra como una implementación alternativa de `descargar_adjunto` (L7) y nada más cambia.
- **API de interoperabilidad** (propuesta de Mauro) — fuera del MVP. Choca con C7 (datos en el
  dispositivo). Queda en la visión.

## Regla

**L5 es el contrato central.** Si alguien quiere cambiar el flujo, que cambie su lego y respete L5.
Mientras L5 no se mueva, dos personas pueden trabajar en paralelo sin pisarse.
