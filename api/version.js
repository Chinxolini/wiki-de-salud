// Qué versión está realmente arriba.
//
// El pie de la web lleva un sello fijo con la fecha y hora en que se desplegó, pero
// ese texto viaja dentro del propio HTML: si el navegador o el CDN sirven una copia
// vieja, el sello viejo viene con ella y no delata nada. Por eso el commit se
// pregunta acá, en runtime: Vercel lo inyecta en el entorno de la función, así que
// esta respuesta viene del despliegue vivo y no de la caché.
//
// No expone nada sensible: el repo es público.

export default function handler(req, res) {
  const sha = process.env.VERCEL_GIT_COMMIT_SHA || null;

  // La primera línea del mensaje de commit alcanza para reconocer la versión de un vistazo.
  const mensaje = (process.env.VERCEL_GIT_COMMIT_MESSAGE || "").split("\n")[0] || null;

  // En `vercel dev` no hay despliegue: se dice, en vez de inventar un sha.
  const entorno = process.env.VERCEL_ENV || "local";

  res.setHeader("cache-control", "no-store");
  return res.status(200).json({
    sha,
    sha_corto: sha ? sha.slice(0, 7) : null,
    rama: process.env.VERCEL_GIT_COMMIT_REF || null,
    mensaje,
    entorno,
    consultado: new Date().toISOString(),
  });
}
