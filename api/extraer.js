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
const MAX_TOKENS = 2000;

// Catálogo cerrado: las únicas entradas posibles. Cualquier otra cosa se rechaza.
const FICHAS = {
  centro_a: { archivo: "ficha-centro_a.html", centro: "Centro Médico San Rafael" },
  centro_b: { archivo: "ficha-centro_b.html", centro: "Laboratorio Clínico Los Andes" },
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

const SYSTEM = `Eres el extractor de un servicio que ordena el historial clínico de una persona.
Recibes una ficha de laboratorio (HTML o texto). Transcribe lo que efectivamente dice y
normaliza cada analito a su nombre y unidad canónicos.

Reglas que no se rompen:
- Transcribe, no interpretes. Cero diagnóstico, cero recomendación, cero juicio clínico.
- Nunca completes un valor que no puedas leer: márcalo "ilegible".
- No corrijas valores clínicamente raros: un valor anómalo bien transcrito es correcto.
- Conserva siempre el valor y la unidad ORIGINALES junto a los canónicos.

Devuelve SOLO un JSON válido, sin texto alrededor, con esta forma exacta:
{
  "centro": string,
  "fecha_documento": string,
  "resultados": [
    {
      "analito_original": string,
      "analito_canonico": string,
      "valor_original": string,
      "unidad_original": string,
      "valor_canonico": string,
      "unidad_canonica": string,
      "confianza": "alta" | "media" | "baja"
    }
  ]
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
  const base = `https://${req.headers.host}`;
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
