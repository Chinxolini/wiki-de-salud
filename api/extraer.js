// Función serverless de Vercel — el mock del pipeline, corriendo de verdad.
//
// Recibe el texto de una ficha clínica (HTML o texto plano) y devuelve el
// registro extraído y normalizado por Claude. La API key vive en la variable
// de entorno ANTHROPIC_API_KEY del proyecto Vercel: nunca toca el navegador.
//
// Guardarraíles para que la demo pública no reviente la cuenta:
//   - Modelo fijo: Haiku. No se puede pedir otro desde afuera.
//   - Entrada limitada a 40.000 caracteres, salida a 2.000 tokens.
//   - Datos sintéticos: esto es una demo. No subir documentos reales.

const MODELO = "claude-haiku-4-5";
const MAX_ENTRADA = 40000;
const MAX_TOKENS = 2000;

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

  const { documento, centro } = req.body || {};
  if (!documento || typeof documento !== "string") {
    return res.status(400).json({ error: "Falta 'documento' (texto de la ficha)." });
  }
  if (documento.length > MAX_ENTRADA) {
    return res.status(413).json({ error: `Documento demasiado largo (máx. ${MAX_ENTRADA} caracteres en la demo).` });
  }

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
        content: `Centro de origen: ${centro || "no informado"}\n\nFicha:\n${documento}`,
      }],
    }),
  });

  if (!r.ok) {
    const detalle = await r.text();
    return res.status(502).json({ error: "La llamada a Claude falló.", detalle: detalle.slice(0, 500) });
  }

  const data = await r.json();
  const texto = (data.content || []).filter(b => b.type === "text").map(b => b.text).join("");

  let registro;
  try {
    // Haiku a veces envuelve el JSON en un fence; se tolera.
    registro = JSON.parse(texto.replace(/^```(json)?\s*/i, "").replace(/\s*```\s*$/, ""));
  } catch {
    return res.status(502).json({ error: "La respuesta no fue JSON válido.", crudo: texto.slice(0, 500) });
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
