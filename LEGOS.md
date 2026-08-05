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
| L8 | **Mail-service** | credenciales en `raw/Credenciales mock chiledao.txt` | IMAP 993 lectura + SMTP 465 envío sobre `mail.chiledao.cl`. **Ya no depende del endpoint HTTP de Mauro**: las credenciales cubren ida y vuelta | ✅ |
| L9 | **Cascada de verificación** | `extraccion/verificar.py` | Haiku extrae → verificador coteja valor por valor contra el original → escala a Sonnet (discrepancia) u Opus (manuscrito/ilegible). Sin humano en el ciclo; **el médico tratante verifica el dossier final** contra los originales de L11 | ✅ |
| L10 | **Render del wiki** | `render/render_wiki.py` | Entrada: L5 · Salida: `wiki-salud.html`, cada valor linkea a su original | ✅ |
| L11 | **Paquete del titular** | `empaquetar.py` | Entrada: L10 + originales · Salida: ZIP con wiki + `originales/` | ✅ |
| L12 | **Entrada del usuario** | `entrada/index.html` | Una pantalla: identidad + centros (leídos de L14) + poder simple + disclaimer IA. Salida: casilla espejo + solicitudes preparadas por canal | ✅ |
| L13 | **Mandato / representación** | `legal/PODER-SIMPLE-mandato.md` | Poder simple electrónico (Ley 20.584 art. 13 b + Ley 19.799) con anexo de autenticidad. Firma simulada en demo; API de Firme.cl en producto | ✅ |
| L14 | **Protocolo por prestador** | `prestadores/protocolos.json` | **El canal es atributo del prestador, no constante del sistema.** El orquestador lo consulta antes de actuar. 4 prestadores levantados | ✅ |
| L15 | **Supresión del caso** | `borrar_caso.py` | Borra casilla + documentos + datos, emite constancia, conserva solo el protocolo agregado sin PII. Cláusula QUINTA del poder | ✅ |

## Piezas bloqueadas (decisión de Ignacio, no se discuten hoy)

- **Carga manual de PDF** como camino de entrada — queda fuera. No afecta a ningún otro lego: si se
  reactiva, entra como una implementación alternativa de `descargar_adjunto` (L7) y nada más cambia.
- **API de interoperabilidad** (propuesta de Mauro) — fuera del MVP. Choca con C7 (datos en el
  dispositivo). Queda en la visión.

## Regla

**L5 es el contrato central.** Si alguien quiere cambiar el flujo, que cambie su lego y respete L5.
Mientras L5 no se mueva, dos personas pueden trabajar en paralelo sin pisarse.
