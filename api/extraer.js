// Función serverless de Vercel — el mock del pipeline, corriendo de verdad.
//
// Está pensada para que los jueces prueben en vivo sin que nadie pueda usar la
// cuenta de terceros. La clave vive en la variable de entorno del proyecto y
// nunca toca el navegador; lo que se protege acá es el USO del endpoint:
//
//   1. Catálogo cerrado. No se acepta texto arbitrario: solo se puede pedir una
//      de las fichas sintéticas que vienen en el repo. Es la diferencia entre
//      una demo y un proxy gratuito a la API de Anthropic.
//   2. Modelo fijo (Haiku) y salida acotada. No se puede escalar desde afuera.
//   3. Límite por IP y límite global de la instancia, para que un script no
//      queme el presupuesto del Lab.

const MODELO = "claude-haiku-4-5";
const MAX_TOKENS = 6000;

// Catálogo cerrado: las únicas entradas posibles. Cualquier otra cosa se rechaza.
const FICHAS = {
  centro_a: { archivo: "ficha-centro_a.html", centro: "Centro Médico San Rafael" },
  centro_b: { archivo: "ficha-centro_b.html", centro: "Hospital Regional de Ñuble" },
  centro_c: { archivo: "ficha-centro_c.html", centro: "Red de Salud Cordillera" },
};

// Cuotas. La instancia serverless se recicla, así que esto no es una defensa
// dura — es un tope razonable que evita el accidente y el script casual.
//
// El límite por IP es generoso a propósito: los jueces evalúan desde el wifi
// del evento y comparten una sola IP tras el NAT. Un tope bajo los cortaría a
// todos juntos, que es el peor resultado posible para una demo. Cada llamada
// cuesta ~medio centavo de dólar; el freno que importa es el límite de gasto
// configurado en la consola de Anthropic, no este contador.
const LIMITE_POR_IP = 60;         // por ventana
const LIMITE_GLOBAL = 400;        // por instancia
const VENTANA_MS = 15 * 60 * 1000;

const usoPorIP = new Map();
let usoGlobal = 0;

function excedeCuota(ip) {
  if (++usoGlobal > LIMITE_GLOBAL) return "La demo alcanzó su límite de uso. Escríbenos y la reactivamos.";
  const ahora = Date.now();
  const previo = usoPorIP.get(ip);
  if (!previo || ahora - previo.desde > VENTANA_MS) {
    usoPorIP.set(ip, { desde: ahora, n: 1 });
    return null;
  }
  if (++previo.n > LIMITE_POR_IP) {
    return "Demasiadas pruebas seguidas. Espera unos minutos e intenta de nuevo.";
  }
  return null;
}

const SYSTEM = `Eres el extractor de un servicio que reúne y ordena el historial clínico de una
persona. Recibes una ficha clínica de un centro de salud (HTML o texto), en el formato y con el
vocabulario que ese centro use. Tu tarea es transcribir lo que el documento dice y normalizarlo a
un esquema único, para que después pueda compararse con lo que digan otros centros.

Normalización: cada elemento conserva SIEMPRE su forma original junto a la canónica.

CRÍTICO — procesas un documento a la vez, sin ver los demás, pero tu salida se une con la de otros
centros. Por eso el valor canónico NO puede depender de cómo venga escrito en este documento: tiene
que ser idéntico al que produzcas para el mismo concepto en cualquier otro. Usa exactamente este
vocabulario, respetando mayúsculas y tildes:

DIAGNÓSTICOS (usa esta forma exacta):
- "Diabetes mellitus tipo 2"  ← DM2, DM tipo 2, diabetes tipo II, diabetes mellitus 2
- "Hipertensión arterial esencial"  ← HTA, HTA esencial, hipertensión esencial
- "Dislipidemia"  ← dislipidemia mixta, hipercolesterolemia, DLP
- "Artrosis"  ← artrosis, gonartrosis, espondiloartrosis (indica la región en el original)

MEDICAMENTOS — "principio_activo" es SIEMPRE el principio activo solo, sin sal, sin dosis, sin
marca y en singular. Nunca uses el nombre comercial ahí:
- "Losartán"  ← COZAAR, Losartán potásico, losartan potasico
- "Metformina"  ← METFORMINA LCH, Glafornil, metformina clorhidrato
- "Atorvastatina", "Paracetamol"  ← ídem, forma simple

EXÁMENES — "analito_canonico" y "unidad_canonica" son fijos por analito. Convierte el valor:
- Leucocitos → unidad canónica "10³/µL". Si viene en /mm³ o /µL, DIVIDE POR 1000
  (7705 /mm³ = 7.705 10³/µL). Es la conversión más frecuente y la que más importa.
- Glucosa en ayunas → "mg/dL" · Hemoglobina → "g/dL" · Creatinina → "mg/dL"
- Colesterol total, Colesterol HDL, Colesterol LDL, Triglicéridos → "mg/dL"
- Hemoglobina glicosilada → "%"  (canónico "Hemoglobina glicosilada", NO "HbA1c" ni "Hemoglobina A1c")
- Proteína C reactiva → "mg/L"
- La unidad canónica se escribe SIEMPRE con la misma grafía: "mg/dL", nunca "mg/dl" ni "MG/DL".

Si un analito, fármaco o diagnóstico no está en estas listas, normalízalo igual: nombre completo,
sin siglas, sin marca, primera letra mayúscula, y la unidad en la grafía convencional del SI.

Procedimientos e imágenes: nombre original y nombre canónico, con el mismo criterio.

Reglas que no se rompen:
- Transcribe, no interpretes. Cero diagnóstico propio, cero recomendación, cero juicio clínico.
- No infieras diagnósticos a partir de síntomas ni de valores de laboratorio. Solo registras los
  diagnósticos que el documento consigna explícitamente.
- En imagenología transcribes la conclusión del informe; nunca reinterpretas la imagen.
- Nunca completes un dato que no puedas leer: agrégalo a "campos_ilegibles" y omítelo del resto.
- No corrijas valores clínicamente raros: un valor anómalo bien transcrito es correcto.
- Si una sección no aparece en el documento, devuélvela como arreglo vacío. No la inventes.

Devuelve SOLO un JSON válido, sin texto alrededor, con esta forma exacta:
{
  "centro": string,
  "fecha_documento": string,
  "diagnosticos":   [{"fecha": string|null, "nombre_original": string, "nombre_canonico": string, "estado": "activo"|"resuelto"|"no_consta", "confianza": "alta"|"media"|"baja"}],
  "alergias":       [{"sustancia": string, "reaccion": string|null, "severidad": "leve"|"moderada"|"severa"|"no_consta", "confianza": "alta"|"media"|"baja"}],
  "medicamentos":   [{"nombre_original": string, "principio_activo": string, "dosis": string|null, "frecuencia": string|null, "vigente": boolean|null, "confianza": "alta"|"media"|"baja"}],
  "atenciones":     [{"fecha": string|null, "tipo": "consulta_ambulatoria"|"urgencia"|"control"|"interconsulta"|"hospitalizacion"|"no_consta", "especialidad": string|null, "motivo_consulta": string, "hallazgos": string|null, "confianza": "alta"|"media"|"baja"}],
  "procedimientos": [{"fecha": string|null, "nombre_original": string, "nombre_canonico": string, "establecimiento": string|null, "confianza": "alta"|"media"|"baja"}],
  "imagenes":       [{"fecha": string|null, "tipo_original": string, "tipo_canonico": string, "region": string|null, "conclusion_informe": string, "confianza": "alta"|"media"|"baja"}],
  "examenes":       [{"fecha": string|null, "analito_original": string, "analito_canonico": string, "valor_original": string, "unidad_original": string, "valor_canonico": string, "unidad_canonica": string, "rango_referencia": string|null, "confianza": "alta"|"media"|"baja"}],
  "campos_ilegibles": [string]
}`;

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Solo POST." });
  }
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) {
    return res.status(500).json({ error: "Falta ANTHROPIC_API_KEY en el entorno del proyecto." });
  }

  const ip = (req.headers["x-forwarded-for"] || "desconocida").split(",")[0].trim();
  const cuota = excedeCuota(ip);
  if (cuota) return res.status(429).json({ error: cuota });

  // Solo se acepta un id del catálogo. Nada de texto libre.
  const { ficha } = req.body || {};
  const elegida = FICHAS[ficha];
  if (!elegida) {
    return res.status(400).json({
      error: "Ficha no válida.",
      disponibles: Object.keys(FICHAS),
    });
  }

  // El documento se lee del propio despliegue, no de lo que mande el cliente.
  // El protocolo se toma de la petición: en `vercel dev` es http y con https fijo el fetch cae.
  const proto = req.headers["x-forwarded-proto"] || "https";
  const base = `${proto}://${req.headers.host}`;
  const doc = await fetch(`${base}/demo/${elegida.archivo}`);
  if (!doc.ok) {
    return res.status(500).json({ error: `No se pudo leer la ficha de demo (${doc.status}).` });
  }
  const documento = await doc.text();

  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: MODELO,
      max_tokens: MAX_TOKENS,
      system: SYSTEM,
      messages: [{
        role: "user",
        content: `Centro de origen: ${elegida.centro}\n\nFicha:\n${documento}`,
      }],
    }),
  });

  if (!r.ok) {
    const detalle = await r.text();
    return res.status(502).json({ error: "La llamada a Claude falló.", detalle: detalle.slice(0, 300) });
  }

  const data = await r.json();
  const texto = (data.content || []).filter(b => b.type === "text").map(b => b.text).join("");

  let registro;
  try {
    registro = JSON.parse(texto.replace(/^```(json)?\s*/i, "").replace(/\s*```\s*$/, ""));
  } catch {
    return res.status(502).json({ error: "La respuesta no fue JSON válido.", crudo: texto.slice(0, 300) });
  }

  return res.status(200).json({
    registro,
    uso: {
      modelo: MODELO,
      tokens_entrada: data.usage?.input_tokens,
      tokens_salida: data.usage?.output_tokens,
    },
  });
}
