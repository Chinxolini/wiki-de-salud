// Función serverless de Vercel — puente hacia el servicio PHP de casillas espejo (Mauro, cPanel).
//
// Mismo patrón que api/extraer.js:
//   1. Catálogo cerrado de acciones. No se reenvía ningún payload arbitrario al PHP: cada
//      campo se valida antes de armar la llamada.
//   2. Cuota por IP y cuota global de la instancia.
//   3. Flag de apagado (PROVISION_ACTIVA): la demo pública no provisiona casillas reales por
//      defecto. Sin el flag, ni siquiera se intenta llamar al PHP.
//
// Minimización de datos: el RUT/cédula del titular NUNCA se envía a este servicio. El PHP
// solo necesita saber a nombre de quién y para qué centros crear la casilla espejo.

import crypto from "node:crypto";

const ACCIONES = new Set([
  "crear-y-provisionar", "estado", "emitir-codigo", "validar-codigo", "enviar-acuerdo",
]);

// ---------- código de firma ----------
//
// El código NO puede nacer ni validarse en el navegador: si vive ahí, cualquiera lo lee
// en las herramientas del navegador y la firma no acredita nada. Y acreditar que la
// persona controla ese correo es justamente lo que sostiene el poder simple del art. 13
// letra b) de la Ley 20.584.
//
// Como las funciones serverless no guardan estado entre invocaciones, en vez de una
// sesión se usa un token firmado: el servidor manda el código SOLO por correo y le
// entrega al navegador un token que es el HMAC de (correo, código, vencimiento). El
// navegador no puede deducir el código desde el token, y al validar el servidor recalcula
// el HMAC y compara. Sin base de datos y sin que el secreto salga del servidor.
const VIGENCIA_CODIGO_MS = 10 * 60 * 1000;

function secretoFirma() {
  // Secreto propio si existe; si no, se deriva de la key del servicio para no exigir una
  // variable nueva. Nunca sale del servidor.
  const base = process.env.FIRMA_SECRETO || process.env.CASILLAS_API_KEY || "";
  return base ? crypto.createHash("sha256").update("firma:" + base).digest() : null;
}

function sellar(email, codigo, vence) {
  const secreto = secretoFirma();
  if (!secreto) return null;
  const firma = crypto.createHmac("sha256", secreto)
    .update(`${email.toLowerCase()}|${codigo}|${vence}`).digest("base64url");
  return `${vence}.${firma}`;
}

function tokenValido(email, codigo, token) {
  if (typeof token !== "string" || !token.includes(".")) return false;
  const vence = Number(token.split(".")[0]);
  if (!Number.isFinite(vence) || Date.now() > vence) return false;
  const esperado = sellar(email, codigo, vence);
  if (!esperado) return false;
  const a = Buffer.from(esperado);
  const b = Buffer.from(token);
  // Comparación de tiempo constante: comparar con === filtra el código dígito a dígito.
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

const RE_EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;
const RE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const RE_CODIGO = /^\d{6}$/;

// Cuotas — mismo espíritu que extraer.js: freno razonable, no defensa dura (la instancia
// serverless se recicla). "estado" es de solo lectura, así que es más laxa que "crear-y-provisionar".
// Generoso a proposito: los jueces evaluan desde el wifi del evento, todos detras del
// mismo NAT, y el boton "Simular caso completo" provisiona una casilla real por clic.
// Con un tope bajo, el sexto juez veria un 429 en vez de la demo — el peor resultado
// posible. Mismo criterio que ya se aplico en extraer.js.
const LIMITE_PROVISION_POR_IP = 30;
const LIMITE_PROVISION_GLOBAL = 200;
const LIMITE_ESTADO_POR_IP = 30;
// "enviar-codigo" / "enviar-acuerdo" comparten un cupo propio: son envíos de correo real
// (no creación de casillas), pero igual de sensibles a abuso (spam) — mismo orden de magnitud
// que "crear-y-provisionar" por IP, con un tope global algo más alto porque no crean recursos en cPanel.
const LIMITE_NOTIFICAR_POR_IP = 10;
const LIMITE_NOTIFICAR_GLOBAL = 100;
const VENTANA_MS = 15 * 60 * 1000;

const usoProvisionPorIP = new Map();
const usoEstadoPorIP = new Map();
const usoNotificarPorIP = new Map();
// Contadores globales como objeto mutable (no variable suelta) para que excedeCuota()
// pueda incrementar el contador correcto según la acción, en vez de asumir uno fijo.
const contadorProvisionGlobal = { n: 0 };
const contadorNotificarGlobal = { n: 0 };

function excedeCuota(mapa, ip, limitePorIP, mensajeIP, limiteGlobal, mensajeGlobal, contadorGlobal) {
  if (limiteGlobal !== null) {
    if (++contadorGlobal.n > limiteGlobal) return mensajeGlobal;
  }
  const ahora = Date.now();
  const previo = mapa.get(ip);
  if (!previo || ahora - previo.desde > VENTANA_MS) {
    mapa.set(ip, { desde: ahora, n: 1 });
    return null;
  }
  if (++previo.n > limitePorIP) return mensajeIP;
  return null;
}

function textoCorto(v, max) {
  return typeof v === "string" && v.trim().length > 0 && v.trim().length <= max;
}

// Valida y devuelve el payload limpio para "crear-y-provisionar", o null si algo no calza.
function validarCrear(body) {
  const { email, nombre, centros, periodo, mandato_texto, firma } = body || {};
  if (!textoCorto(email, 254) || !RE_EMAIL.test(email.trim())) return null;
  if (!textoCorto(nombre, 80)) return null;
  if (!Array.isArray(centros) || centros.length === 0 || centros.length > 5) return null;
  if (!centros.every(c => textoCorto(c, 80))) return null;
  if (!textoCorto(periodo, 120)) return null;
  if (!textoCorto(mandato_texto, 4000)) return null;
  if (!textoCorto(firma, 80)) return null;
  return {
    email: email.trim(),
    nombre: nombre.trim(),
    centros: centros.map(c => c.trim()),
    periodo: periodo.trim(),
    mandato_texto: mandato_texto.trim(),
    firma: firma.trim(),
  };
}

// Valida el body de "emitir-codigo": { email }. El código lo genera el servidor.
function validarEmitir(body) {
  const { email } = body || {};
  if (!textoCorto(email, 254) || !RE_EMAIL.test(email.trim())) return null;
  return { email: email.trim() };
}

// Valida el body de "validar-codigo": { email, codigo, token }.
function validarValidacion(body) {
  const { email, codigo, token } = body || {};
  if (!textoCorto(email, 254) || !RE_EMAIL.test(email.trim())) return null;
  if (typeof codigo !== "string" || !RE_CODIGO.test(codigo.trim())) return null;
  if (!textoCorto(token, 200)) return null;
  return { email: email.trim(), codigo: codigo.trim(), token: token.trim() };
}

// Valida el body de "enviar-acuerdo": { email, texto } — texto máx 12KB (igual que el PHP).
function validarEnviarAcuerdo(body) {
  const { email, texto } = body || {};
  if (!textoCorto(email, 254) || !RE_EMAIL.test(email.trim())) return null;
  if (typeof texto !== "string" || texto.trim().length === 0) return null;
  if (Buffer.byteLength(texto.trim(), "utf8") > 12 * 1024) return null;
  return { email: email.trim(), texto: texto.trim() };
}

async function llamarPHP(base, apiKey, action, payload) {
  const controlador = new AbortController();
  const corte = setTimeout(() => controlador.abort(), 20000);
  try {
    const r = await fetch(`${base}?action=${action}`, {
      method: "POST",
      headers: { "content-type": "application/json", "X-Api-Key": apiKey },
      body: JSON.stringify(payload),
      signal: controlador.signal,
    });
    const sobre = await r.json().catch(() => null);
    if (!r.ok || !sobre || sobre.ok === false) {
      const msg = sobre?.message || `El servicio de casillas respondió ${r.status}.`;
      return { ok: false, error: msg, detalle: sobre?.data?.detalle };
    }
    return { ok: true, data: sobre.data };
  } catch (err) {
    const msg = err?.name === "AbortError" ? "El servicio de casillas no respondió a tiempo." :
      "No se pudo contactar al servicio de casillas.";
    return { ok: false, error: msg };
  } finally {
    clearTimeout(corte);
  }
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Solo POST." });
  }

  const ip = (req.headers["x-forwarded-for"] || "desconocida").split(",")[0].trim();
  const { accion } = req.body || {};
  if (!ACCIONES.has(accion)) {
    return res.status(400).json({
      error: "Acción no válida.",
      disponibles: Array.from(ACCIONES),
    });
  }

  if (accion === "estado") {
    const cuota = excedeCuota(usoEstadoPorIP, ip, LIMITE_ESTADO_POR_IP,
      "Demasiadas consultas seguidas. Espera unos minutos e intenta de nuevo.", null, null, null);
    if (cuota) return res.status(429).json({ error: cuota });
  } else if (accion === "emitir-codigo" || accion === "enviar-acuerdo") {
    const cuota = excedeCuota(usoNotificarPorIP, ip, LIMITE_NOTIFICAR_POR_IP,
      "Demasiados envíos seguidos. Espera unos minutos e intenta de nuevo.",
      LIMITE_NOTIFICAR_GLOBAL, "La demo alcanzó su límite de envíos. Escríbenos y la reactivamos.",
      contadorNotificarGlobal);
    if (cuota) return res.status(429).json({ error: cuota });
  } else {
    const cuota = excedeCuota(usoProvisionPorIP, ip, LIMITE_PROVISION_POR_IP,
      "Demasiadas pruebas seguidas. Espera unos minutos e intenta de nuevo.",
      LIMITE_PROVISION_GLOBAL, "La demo alcanzó su límite de uso. Escríbenos y la reactivamos.",
      contadorProvisionGlobal);
    if (cuota) return res.status(429).json({ error: cuota });
  }

  // "validar-codigo" se resuelve entero acá dentro, sin hablar con el PHP: es puro HMAC.
  // Por eso va ANTES del interruptor — si dependiera de PROVISION_ACTIVA, apagar la
  // provisión dejaría la firma sin poder validarse y el flujo entero muerto.
  if (accion === "validar-codigo") {
    const datos = validarValidacion(req.body);
    if (!datos) return res.status(400).json({ error: "Datos incompletos." });
    if (!secretoFirma()) {
      return res.status(500).json({ error: "Falta el secreto de firma en el servidor." });
    }
    const valido = tokenValido(datos.email, datos.codigo, datos.token);
    // Mismo cuerpo y mismo tiempo de respuesta para válido e inválido, salvo el booleano.
    return res.status(200).json({ valido });
  }

  // PROVISION_ACTIVA es el interruptor único para cualquier llamada saliente al PHP de
  // casillas, no solo para "crear-y-provisionar": hoy ya se aplica igual a "estado" (solo
  // lectura), así que "emitir-codigo"/"enviar-acuerdo" mantienen el mismo criterio por
  // coherencia, aunque no aprovisionen nada — evita un modo mixto donde el flag apagado
  // igual permite tráfico saliente real hacia el servicio de casillas.
  if (process.env.PROVISION_ACTIVA !== "1") {
    return res.status(503).json({ error: "Provisión desactivada.", fallback: true });
  }

  const base = process.env.CASILLAS_API_URL;
  const apiKey = process.env.CASILLAS_API_KEY;
  if (!base || !apiKey) {
    return res.status(500).json({ error: "Falta configuración del servicio de casillas.", fallback: true });
  }

  if (accion === "estado") {
    const { guid } = req.body || {};
    if (typeof guid !== "string" || !RE_UUID.test(guid)) {
      return res.status(400).json({ error: "guid no válido." });
    }
    const controlador = new AbortController();
    const corte = setTimeout(() => controlador.abort(), 20000);
    try {
      const r = await fetch(`${base}?action=estado&guid=${encodeURIComponent(guid)}`, {
        headers: { "X-Api-Key": apiKey },
        signal: controlador.signal,
      });
      const sobre = await r.json().catch(() => null);
      if (!r.ok || !sobre || sobre.ok === false) {
        return res.status(502).json({ error: "No se pudo consultar el estado.", fallback: true });
      }
      return res.status(200).json(sobre.data);
    } catch {
      return res.status(502).json({ error: "El servicio de casillas no respondió.", fallback: true });
    } finally {
      clearTimeout(corte);
    }
  }

  if (accion === "emitir-codigo") {
    const payload = validarEmitir(req.body);
    if (!payload) {
      return res.status(400).json({ error: "Correo no válido." });
    }
    if (!secretoFirma()) {
      return res.status(500).json({ error: "Falta el secreto de firma en el servidor." });
    }

    // El código nace acá, con azar criptográfico, y solo viaja por correo.
    const codigo = String(crypto.randomInt(0, 1000000)).padStart(6, "0");
    const vence = Date.now() + VIGENCIA_CODIGO_MS;
    const token = sellar(payload.email, codigo, vence);

    const envio = await llamarPHP(base, apiKey, "notificar", {
      email: payload.email,
      tipo: "codigo",
      datos: { codigo },
    });

    // `enviado` viene del mail() del servidor: significa "aceptado para envío", NO
    // "llegó a la bandeja". Puede terminar en spam. Por eso el flujo nunca depende de
    // que la persona reciba el correo para poder seguir.
    const enviado = envio.ok && !!envio.data?.enviado;

    // Afordancia de demostración: con DEMO_CODIGO_VISIBLE=1 el código vuelve al
    // navegador para que un juez pruebe sin abrir su correo. En un producto real esta
    // variable no existe: es exactamente lo que anula la garantía de la firma.
    const cuerpo = { token, enviado, expira_en: vence };
    if (process.env.DEMO_CODIGO_VISIBLE === "1") cuerpo.codigo_demo = codigo;

    return res.status(200).json(cuerpo);
  }

  if (accion === "enviar-acuerdo") {
    const payload = validarEnviarAcuerdo(req.body);
    if (!payload) {
      return res.status(400).json({ error: "Datos incompletos o fuera de los límites permitidos." });
    }
    const envio = await llamarPHP(base, apiKey, "notificar", {
      email: payload.email,
      tipo: "acuerdo",
      datos: { texto: payload.texto },
    });
    if (!envio.ok) {
      return res.status(502).json({ error: envio.error, fallback: true });
    }
    return res.status(200).json({ enviado: !!envio.data?.enviado });
  }

  // accion === "crear-y-provisionar"
  const payload = validarCrear(req.body);
  if (!payload) {
    return res.status(400).json({ error: "Datos de la solicitud incompletos o fuera de los límites permitidos." });
  }

  const crear = await llamarPHP(base, apiKey, "crear", payload);
  if (!crear.ok) {
    return res.status(502).json({ error: crear.error, fallback: true });
  }
  const { guid } = crear.data || {};
  if (typeof guid !== "string" || !guid) {
    return res.status(502).json({ error: "El servicio de casillas no devolvió un identificador.", fallback: true });
  }

  const provisionar = await llamarPHP(base, apiKey, "provisionar", { guid });
  if (!provisionar.ok) {
    return res.status(502).json({ error: provisionar.error, detalle: provisionar.detalle, fallback: true });
  }

  const { direccion, status } = provisionar.data || {};
  if (!direccion) {
    return res.status(502).json({ error: "El servicio de casillas no devolvió una dirección.", fallback: true });
  }

  return res.status(200).json({ guid, direccion, status });
}
