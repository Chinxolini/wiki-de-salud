# L14 — Registro de protocolo por prestador

**El canal no es una constante del sistema: es un atributo del prestador.**

Este lego apareció el 5-ago al verificar que el Hospital del Profesor no recibe solicitudes por
correo sino por un formulario en su web. Hasta entonces L8 asumía "enviamos correo → responden a la
casilla espejo". Ese supuesto es falso en la ida.

## El hallazgo, en una línea

**Ninguno de los 4 prestadores levantados recibe solicitudes de ficha por correo.** Tres reciben por
formulario web y uno presencial por sede. Pero **los tres del formulario responden al correo que se
indica en ese formulario** — verificado con una solicitud real al CHP el 4-ago, que respondió el
mismo día a la casilla indicada.

> **La ida está fragmentada (formulario o mostrador); la vuelta es correo.**

Eso no rompe la arquitectura: la **valida**. La casilla espejo sigue siendo el punto de recepción
correcto, y es el dato que se escribe en cada formulario. Lo que cambia es que el envío inicial no
es automatizable hoy: es un paso asistido, y así se declara.

## Cómo lo consume el orquestador

Antes de actuar, el agente lee `protocolos.json` y elige según `canal.tipo`:

| `canal.tipo` | Qué hace el agente | Automatizable |
|---|---|---|
| `correo` | Llama `enviar_correo` desde la casilla espejo | Sí |
| `formulario_web` | Genera el texto de la solicitud + los datos a pegar, y marca el caso como **acción asistida pendiente**. La casilla espejo va como correo de contacto | No (hoy) |
| `presencial` | Genera la carta formal imprimible + checklist de documentos | No |

En los tres casos, la **recepción** es idéntica: la respuesta llega a la casilla espejo y entra al
pipeline ya construido (L4–L7 → L10 → L11).

## Por qué esto es un activo y no una deuda

1. **Es el catálogo de protocolos** que Mauro quería ir descubriendo caso a caso. Ya está empezado,
   estructurado y medible.
2. **Desde el 1-dic-2026 es exigible**: el art. 14 ter letra c) de la Ley 21.719 obliga a cada
   responsable a publicar y mantener operativo un canal (correo, formulario de contacto o medio
   equivalente) para recibir solicitudes de titulares. Un canal publicado que no existe o no
   responde es infracción leve (hasta 5.000 UTM); obstaculizar el acceso es infracción **grave**
   (hasta 10.000 UTM, art. 34 ter e + 35 b). Ver
   `construccion/docs/citas-obligacion-entrega-digital.md` §4.
3. **Es la medición C5**: cada fila lleva su propio registro de días hasta la primera respuesta y
   hasta la entrega efectiva. Es la cifra propia del pitch.

## Estado de la medición C5

| Prestador | Canal | Solicitud enviada | 1ª respuesta | Entrega |
|---|---|---|---|---|
| Hospital del Profesor | formulario web ✅ verificado | 4-ago | **mismo día** (0-1 d) | ⏳ pendiente |
| HCUCH | formulario web (OIRS MINSAL) | — | — | — |
| IntegraMédica | formulario web | — | — | — |
| RedSalud | presencial por sede | — | — | — |

## Límites conocidos (se declaran, no se ocultan)

- El envío por formulario web **no está automatizado** en el MVP. Se puede automatizar después con
  navegación asistida, pero hacerlo hoy sería una promesa sin respaldo.
- RedSalud exige solicitud **por cada sede** donde hubo atención, pese a tener ficha unificada
  internamente para sus profesionales. Es el caso de fricción máxima y sirve de ejemplo del problema.
- Los plazos declarados (5 a 20 días hábiles) son los que dice cada prestador, no los medidos. Solo
  el CHP tiene dato propio.
