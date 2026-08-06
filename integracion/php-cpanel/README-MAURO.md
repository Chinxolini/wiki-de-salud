# api_agente.php — instrucciones para Mauro

## 1. Copiar el archivo

Copia `api_agente.php` a la **raíz** del repo (junto a `api.php`, `config.php`, `autoload.php`).
No toca nada más: reutiliza tal cual `lib/store.php` y el módulo `EmailProvisioner`.

## 2. Agregar la clave del agente al `.env`

En el `.env` del servidor (el que ya tiene `CPANEL_HOST`, `CPANEL_USER`, etc.), agrega una línea:

```
AGENTE_API_KEY=<genera-una-clave-larga-y-aleatoria-nueva>
```

Puedes generarla en tu máquina con:

```powershell
[guid]::NewGuid().ToString() + [guid]::NewGuid().ToString()
```

Esta clave es **distinta** de la que usa `api.php` — no la reutilices.

## 3. ROTAR la clave de cPanel — urgente

`api.php` tiene una API key **hardcodeada en el código** (la constante `$API_KEY` de la línea 4),
y ese archivo vive en el repo público: esa clave está expuesta y debe considerarse quemada.

**Antes de seguir usando el sistema en producción**: entra a cPanel y rota/regenera esa clave
(o cambia el password del usuario asociado), y mueve el valor nuevo a `.env` en vez de dejarlo en el código.
Lo mismo aplica a `CPANEL_PASS` si ya se filtró en algún commit anterior.

## 4. Probar cada acción (PowerShell, sin `&&`)

Reemplaza `TU_HOST` por el dominio real y `TU_CLAVE` por el valor de `AGENTE_API_KEY`.

**ping** (GET, no requiere body):

```powershell
$headers = @{ "X-Api-Key" = "TU_CLAVE" }
Invoke-RestMethod -Uri "https://TU_HOST/api_agente.php?action=ping" -Headers $headers
```

**crear** (POST JSON):

```powershell
$headers = @{ "X-Api-Key" = "TU_CLAVE"; "Content-Type" = "application/json" }
$body = @{
  email         = "paciente@ejemplo.cl"
  nombre        = "Juana Pérez"
  centros       = @("Hospital X", "Clínica Y")
  periodo       = "2024-2026"
  mandato_texto = "Texto del mandato ya generado por el frontend"
  firma         = "firma-electronica-simple-base64-o-texto"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://TU_HOST/api_agente.php?action=crear" -Method POST -Headers $headers -Body $body
```

Devuelve `{guid, status}`. Guarda el `guid`, lo necesitas para los siguientes pasos.

**provisionar** (POST JSON, usa el guid del paso anterior):

```powershell
$body = @{ guid = "EL-GUID-QUE-TE-DEVOLVIO-CREAR" } | ConvertTo-Json
Invoke-RestMethod -Uri "https://TU_HOST/api_agente.php?action=provisionar" -Method POST -Headers $headers -Body $body
```

Crea la casilla real en cPanel (síncrono, puede tardar unos segundos). Devuelve `{guid, status, direccion}`.
Si lo corres dos veces con el mismo guid, la segunda vez devuelve la misma `direccion` sin volver a crear nada (idempotente).

**estado** (GET):

```powershell
Invoke-RestMethod -Uri "https://TU_HOST/api_agente.php?action=estado&guid=EL-GUID" -Headers $headers
```

Devuelve solo `{guid, status, direccion, expires_at}` — nunca password, ip, mandato ni run.

**eliminar** (POST JSON):

```powershell
$body = @{ guid = "EL-GUID" } | ConvertTo-Json
Invoke-RestMethod -Uri "https://TU_HOST/api_agente.php?action=eliminar" -Method POST -Headers $headers -Body $body
```

Borra la casilla en cPanel (si existía) y elimina el registro completo (y su cédula, si tenía) del store.
Devuelve `{guid, borrado:true}`.

## 5. Pendiente — reactivar el gate de CLI en `run_provisioning.php`

En `run_provisioning.php` el chequeo que bloquea la ejecución vía navegador está comentado:

```php
// if (php_sapi_name() !== 'cli') {
//     http_response_code(403);
//     exit('Este script solo puede ejecutarse por línea de comandos.');
// }
```

Con `api_agente.php` ya no se necesita correr ese script por HTTP para nada — el flujo de
aprovisionamiento pasa por `?action=provisionar`. Descomenta esas líneas para que
`run_provisioning.php` vuelva a ser solo-CLI y no quede como endpoint HTTP sin autenticación.
