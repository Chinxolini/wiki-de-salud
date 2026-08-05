# Deploy a Vercel

El repo ya está listo: `vercel.json` sirve el formulario en `/` y `api/extraer.js` es la función
serverless que llama a Claude (Haiku fijo, entrada y salida acotadas — no se puede pedir otro
modelo desde afuera).

## Pasos (una vez)

1. **Subir el repo a GitHub** (la cuenta ya está vinculada a Vercel):

```bash
gh auth login -h github.com
```

```bash
cd "C:/Users/ignac/OneDrive/Prueba Claude Cowork/IG-Lab/Personal/IMPACTLAB/construccion/mvp" && gh repo create wiki-de-salud --private --source . --push
```

2. **Importar en Vercel**: vercel.com → Add New → Project → elegir `wiki-de-salud` → Deploy.
   Sin configuración extra: detecta el estático y la carpeta `api/` solo.

3. **La API key** (el único paso que importa): en el proyecto de Vercel →
   Settings → Environment Variables →

   | Name | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | la key del Lab |

   y **Redeploy**. La key vive solo en el servidor de Vercel; el navegador nunca la ve.

## Probar

- `https://<proyecto>.vercel.app/` → el formulario.
- Llenar y enviar → en la pantalla de confirmación aparece **"Míralo funcionar ahora"**: el botón
  manda la ficha sintética del centro A a `/api/extraer` y pinta la tabla de analitos
  normalizados con el conteo de tokens. Esa card solo aparece cuando la página corre servida
  (en `file://` se oculta sola, porque no hay backend).

## Costos

Cada click del demo ≈ 3.500 tokens de entrada + ~600 de salida en Haiku ≈ **medio centavo de
dólar**. Con los ~$4.85 restantes alcanza para ~1.000 clicks. Aun así: la URL no se publica en
ningún lado masivo; es para la demo y el video.

## Después del Lab

- Rotar la API key (ya está en PENDIENTES).
- Pausar o borrar el proyecto de Vercel si no se sigue usando.
