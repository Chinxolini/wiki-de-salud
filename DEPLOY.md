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

## Sello de versión

Antes de commitear lo que se va a desplegar:

```powershell
python tools/sellar_version.py
```

Escribe la fecha y hora en el pie de la web. Al lado, la página muestra el commit que
responde `/api/version` — ese viene del despliegue vivo, así que no puede salir de una
copia cacheada del navegador.

Para verificar desde afuera que arriba está lo nuestro:

```powershell
git rev-parse --short HEAD
curl -s https://wiki-de-salud.vercel.app/api/version
```

Si el `sha_corto` de la respuesta es igual al `HEAD` local, producción sirve esta versión.

## Integración casillas (cPanel)

`api/casilla.js` llama al servicio PHP de Mauro (dominio `chiledao.cl`) para provisionar la
casilla espejo real. Por defecto está **desactivada**: sin `PROVISION_ACTIVA=1` responde 503
con `fallback: true` y el formulario sigue con el cálculo sintético de siempre.

Variables nuevas (Vercel → Settings → Environment Variables, o por CLI):

| Name | Value |
|---|---|
| `CASILLAS_API_URL` | `https://losinmortales.chiledao.cl/api_agente.php` |
| `CASILLAS_API_KEY` | la key del servicio de Mauro |
| `PROVISION_ACTIVA` | `1` para activar; cualquier otro valor (u omitirla) la deja apagada |

Agregarlas por CLI (PowerShell, sin `&&`, con `;`):

```powershell
vercel env add CASILLAS_API_URL production
vercel env add CASILLAS_API_KEY production
vercel env add PROVISION_ACTIVA production
```

Y luego `vercel --prod` (o Redeploy desde el dashboard) para que tomen efecto.

**Validado end-to-end el 5-ago 20:20**: el formulario provisiona la casilla real
(`nombre@chiledao.cl`), `estado` la consulta sin exponer password ni RUN, y `borrar_caso.py`
la elimina del cPanel y del registro. La app de Mauro vive en el subdominio
`losinmortales.chiledao.cl`, no en la raíz del dominio.

## Después del Lab

- Rotar la API key (ya está en PENDIENTES).
- Pausar o borrar el proyecto de Vercel si no se sigue usando.
