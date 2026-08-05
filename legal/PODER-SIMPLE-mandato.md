---
title: Poder simple para solicitar ficha clínica — texto operativo + soporte de autenticidad
type: operational
date-created: 2026-08-05
estado: listo para usar (firma simulada en la demo)
---

# L13 — El mandato

Cierra el hueco 2 de la auditoría. Dos partes: **el texto que firma la persona** (§2) y **lo que
nuestro sistema registra para que esa firma sea defendible** (§3). Sin §3, §2 es un checkbox.

---

## 1. La norma, literal

**Ley 20.584, art. 13, letra b** — verificado contra `raw/LEY 20584 DERECHOS DE LOS PACIENTES.txt`,
líneas 346-348:

> "b) A **un tercero debidamente autorizado por el titular, mediante poder simple otorgado ante
> notario o firmado a través de un sistema electrónico que garantice su autenticidad**, de
> conformidad con lo dispuesto a la ley N° 19.799, sobre documentos electrónicos, firma electrónica
> y servicios de certificación de dicha firma."

Tres consecuencias que mandan sobre todo lo demás:

1. **La vía electrónica es alternativa plena a la notarial.** El "o" es disyuntivo. No hay que ir a
   notaría.
2. **El estándar no es "firma electrónica avanzada"**, es "sistema electrónico que garantice su
   autenticidad… de conformidad con la Ley 19.799". La **firma electrónica simple** está definida y
   reconocida en esa ley y **no exige certificador acreditado**. Lo exigible es que el sistema
   *garantice la autenticidad*, y eso se acredita con evidencia, no con un sello.
3. **Un checkbox de términos y condiciones no cumple.** No individualiza al firmante, no consta el
   contenido de lo que autoriza, y no deja rastro verificable. El "término de condiciones" que
   propuso Mauro sería impugnable por cualquier prestador.

---

## 2. El texto del poder

> **PODER SIMPLE PARA SOLICITAR Y RECIBIR COPIA DE FICHA CLÍNICA**
>
> En [CIUDAD], a [FECHA].
>
> Yo, **[NOMBRE COMPLETO DEL TITULAR]**, cédula nacional de identidad N° **[RUT TITULAR]**,
> domiciliado/a en [DOMICILIO], en adelante "el titular", vengo en conferir **poder simple** a
> **[NOMBRE DEL MANDATARIO]**, [RUT MANDATARIO], en adelante "el mandatario", para que en mi nombre
> y representación ejerza las facultades que a continuación se indican.
>
> **PRIMERO. Facultades conferidas.** El mandatario queda facultado para:
>
> a) Solicitar, ante los prestadores de salud individualizados en la cláusula SEGUNDA, copia íntegra
>    de mi ficha clínica y de los antecedentes que de mí obren en su poder, conforme al artículo 13
>    de la Ley N° 20.584;
> b) Recibir dicha copia, en soporte físico o electrónico, y acusar recibo de ella;
> c) Ejercer, respecto de esos mismos antecedentes, el **derecho de acceso** que reconoce la
>    legislación de protección de datos personales, y presentar las reclamaciones que procedan ante
>    la autoridad competente en caso de denegación, silencio o entrega defectuosa;
> d) Efectuar las gestiones administrativas accesorias que sean estrictamente necesarias para lo
>    anterior, incluyendo completar formularios de contacto, acompañar documentos de identidad y
>    designar una casilla de correo electrónico para la recepción de las respuestas.
>
> **SEGUNDO. Prestadores comprendidos.** Este poder se otorga exclusivamente respecto de los
> siguientes prestadores: [LISTA DE PRESTADORES]. No se extiende a ningún otro.
>
> **TERCERO. Finalidad única y prohibición de uso ulterior.** Los antecedentes obtenidos serán
> utilizados **únicamente** para consolidarlos y entregármelos a mí. El mandatario **no queda
> facultado** para cederlos, comunicarlos, publicarlos ni tratarlos con ninguna finalidad distinta,
> ni para consentir tratamientos por cuenta de terceros.
>
> **CUARTO. Casilla de correo designada.** Para la recepción de las respuestas de los prestadores se
> designa la casilla **[CASILLA ESPEJO]**, creada a mi nombre. Toda comunicación recibida en ella me
> será reenviada íntegramente a mi correo personal **[CORREO DEL TITULAR]**.
>
> **QUINTO. Supresión al término del encargo.** Cumplido el encargo y entregados los antecedentes,
> el mandatario **suprimirá** de sus sistemas la casilla designada y la totalidad de los documentos
> y datos personales obtenidos, conservando únicamente un registro estadístico **sin datos
> personales** relativo al plazo y formato de respuesta de cada prestador. Se me entregará
> constancia de la supresión con su fecha y hora.
>
> **SEXTO. Vigencia y revocación.** Este poder rige por **[N] días** contados desde su fecha, o
> hasta el cumplimiento del encargo si ello ocurriere antes. **Puedo revocarlo en cualquier momento,
> sin expresión de causa**, mediante comunicación escrita al mandatario, incluso por correo
> electrónico. La revocación produce efectos desde su recepción y obliga a la supresión inmediata
> conforme a la cláusula QUINTA.
>
> **SÉPTIMO. Forma de otorgamiento.** Este poder se otorga y firma **a través de un sistema
> electrónico que garantiza su autenticidad**, en los términos del artículo 13 letra b) de la Ley
> N° 20.584 y de la Ley N° 19.799 sobre documentos electrónicos y firma electrónica. La constancia
> técnica de la firma se incorpora como **Anexo de Autenticidad** y forma parte integrante de este
> instrumento.
>
> **OCTAVO. Declaración del titular.** Declaro que la información que he proporcionado es efectiva,
> que soy la persona cuya ficha clínica se solicita, y que comprendo el alcance de las facultades
> que confiero.
>
> \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
> **[NOMBRE COMPLETO DEL TITULAR]**
> C.I. N° [RUT TITULAR]
> Firmado electrónicamente el [FECHA Y HORA] — ver Anexo de Autenticidad

---

## 3. Anexo de Autenticidad — lo que hace defendible la firma

La ley pide un sistema **que garantice la autenticidad**. No define cómo. Esto es lo que el sistema
registra y adjunta al poder, y es lo que se muestra si un prestador lo objeta:

| Elemento | Qué se registra | Qué acredita |
|---|---|---|
| **Identidad declarada** | Nombre, RUT, correo, teléfono | A quién se atribuye la firma |
| **Documento de identidad** | Imagen de la cédula por ambos lados | Correspondencia entre el declarante y una cédula real |
| **Prueba de control del correo** | Código de un solo uso enviado al correo del titular y validado; hora de emisión y de validación | Que quien firmó controla la casilla que declaró — el elemento nuclear de la FES |
| **Manifestación de voluntad** | Texto íntegro del poder mostrado en pantalla antes de firmar + marca de aceptación expresa (no premarcada) | Que consintió *ese* contenido, no unos términos genéricos |
| **Integridad** | Hash SHA-256 del PDF/HTML del poder al momento de firmar | Que el documento no se alteró después |
| **Sello de tiempo** | Fecha y hora UTC de cada paso | Cronología verificable |
| **Trazas técnicas** | IP, user-agent, identificador de sesión | Contexto de la firma |
| **Constancia de envío** | Copia íntegra del poder firmado enviada al correo del titular | Que el titular tiene el mismo documento en su poder |

**Esto es firma electrónica simple hecha bien.** No es firma avanzada y no hay que decir que lo es.

### El plan de dos velocidades

- **Demo (hoy)**: firma simulada con este mismo anexo generado, para que se vea el mecanismo
  completo sin datos reales.
- **Producto**: se conecta un proveedor. **Firme.cl expone API REST** con sandbox gratuito, SDKs y
  webhooks (`raw/Firme.cl API.txt`). ⚠️ **Corrección de la cifra que veníamos usando**: la API es
  **desde $50.000/mes según volumen**, no $800 por documento — los $800 corresponden al producto de
  firma unitaria. En unit economics, la API conviene desde ~60 documentos/mes.
- **Servicio propio**: técnicamente viable con la tabla de arriba, porque la FES no exige
  certificador acreditado. **No se construye hoy** y no cabe en la ventana. Queda declarado como
  camino de reducción de costo, no como capacidad actual.

---

## 4. Lo que NO se puede decir

⛔ "Verificamos identidad con Clave Única" — **no está abierta a privados**.
⛔ "Usamos firma electrónica avanzada" — es firma simple.
⛔ "Este poder ya fue aceptado por los prestadores" — **no hay precedente confirmado** (tampoco en
contra). La ley lo permite; la práctica no está testeada. Eso es exactamente lo que mide C5.
⛔ "Está certificado" / "tiene validez notarial" — no lo está y no la tiene; tiene validez legal por
una vía distinta.

✅ Lo defendible: *"El artículo 13 letra b de la Ley 20.584 admite el poder simple firmado por un
sistema electrónico que garantice su autenticidad. Nosotros gestionamos ese mandato y guardamos la
evidencia que lo sostiene: control del correo verificado, cédula, hash del documento y sello de
tiempo. En producto se apoya en un proveedor con API. Y estamos midiendo, con solicitudes reales,
cómo responde cada prestador."*
