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

const ACCIONES = new Set(["crear-y-provisionar", "estado"]);

const RE_EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;
const RE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Cuotas — mismo espíritu que extraer.js: freno razonable, no defensa dura (la instancia
// serverless se recicla). "estado" es de solo lectura, así que es más laxa que "crear-y-provisionar".
const LIMITE_PROVISION_POR_IP = 5;
const LIMITE_PROVISION_GLOBAL = 50;
const LIMITE_ESTADO_POR_IP = 30;
const VENTANA_MS = 15 * 60 * 1000;

const usoProvisionPorIP = new Map();
const usoEstadoPorIP = new Map();
let usoProvisionGlobal = 0;

function excedeCuota(mapa, ip, limitePorIP, mensajeIP, limiteGlobal, mensajeGlobal) {
  if (limiteGlobal !== null) {
    if (++usoProvisionGlobal > limiteGlobal) return mensajeGlobal;
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
      "Demasiadas consultas seguidas. Espera unos minutos e intenta de nuevo.", null, null);
    if (cuota) return res.status(429).json({ error: cuota });
  } else {
    const cuota = excedeCuota(usoProvisionPorIP, ip, LIMITE_PROVISION_POR_IP,
      "Demasiadas pruebas seguidas. Espera unos minutos e intenta de nuevo.",
      LIMITE_PROVISION_GLOBAL, "La demo alcanzó su límite de uso. Escríbenos y la reactivamos.");
    if (cuota) return res.status(429).json({ error: cuota });
  }

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
