<?php
/**
 * api_agente.php
 *
 * Endpoint pensado para que un agente (no un navegador) opere el flujo de
 * "Los Inmortales" de punta a punta: crear solicitud, disparar el
 * aprovisionamiento de correo, consultar estado y eliminar un expediente.
 *
 * Copiar a la raíz del repo (junto a api.php). No requiere composer ni
 * dependencias nuevas: reutiliza autoload.php, config.php, lib/store.php y
 * el módulo EmailProvisioner tal como los usa run_provisioning.php.
 *
 * Autenticación: SOLO header X-Api-Key, comparado con hash_equals contra
 * AGENTE_API_KEY definida en .env. Nunca se acepta la key por querystring.
 */

header('Content-Type: application/json; charset=utf-8');
date_default_timezone_set('America/Santiago');

require_once __DIR__ . '/autoload.php';
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/lib/store.php';

use LosInmortales\EmailProvisioner\Config;
use LosInmortales\EmailProvisioner\CPanelClient;
use LosInmortales\EmailProvisioner\MailSender;
use LosInmortales\EmailProvisioner\RequestRepository;
use LosInmortales\EmailProvisioner\Logger;
use LosInmortales\EmailProvisioner\UsernameGenerator;
use LosInmortales\EmailProvisioner\PasswordGenerator;
use LosInmortales\EmailProvisioner\EmailProvisioner;

/**
 * Envoltura de respuesta idéntica a la de api.php.
 */
function out($d, $m = 'OK', $ok = true, $httpCode = null)
{
    if ($httpCode !== null) {
        http_response_code($httpCode);
    }
    echo json_encode(
        ["ok" => $ok, "version" => "1.0", "timestamp" => date('c'), "message" => $m, "data" => $d],
        JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE
    );
    exit;
}

/**
 * Corta la ejecución con un 500 en JSON, sin exponer el stack trace.
 */
function fail500(\Throwable $e)
{
    // El detalle real queda solo en error_log del servidor, nunca en la respuesta.
    error_log('[api_agente] ' . $e->getMessage() . ' en ' . $e->getFile() . ':' . $e->getLine());
    out([], 'Error interno del servidor', false, 500);
}

// --- Autenticación: solo por header, nunca por querystring -----------------

try {
    Config::load(__DIR__ . '/.env');
} catch (\Throwable $e) {
    fail500($e);
}

$agenteKey = Config::get('AGENTE_API_KEY', '');
$recibida = $_SERVER['HTTP_X_API_KEY'] ?? '';

if ($agenteKey === '' || $recibida === '' || !hash_equals((string)$agenteKey, (string)$recibida)) {
    out([], 'Unauthorized', false, 401);
}

// --- Helpers locales ---------------------------------------------------------

/**
 * Valida que un string sea un GUID v4 (el mismo formato que genera li_generate_guid()).
 */
function esGuidValido($guid): bool
{
    return is_string($guid) && preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i', $guid) === 1;
}

/**
 * Lee y decodifica el body JSON de la petición, validando tamaño y Content-Type.
 * Corta con out(...) si algo no cumple.
 */
function leerBodyJson(): array
{
    $contentType = $_SERVER['CONTENT_TYPE'] ?? $_SERVER['HTTP_CONTENT_TYPE'] ?? '';
    if (stripos($contentType, 'application/json') === false) {
        out([], 'Content-Type debe ser application/json', false, 400);
    }

    $raw = file_get_contents('php://input');
    if ($raw === false) {
        $raw = '';
    }

    if (strlen($raw) >= 32 * 1024) {
        out([], 'Cuerpo de la petición demasiado grande (máximo 32KB)', false, 400);
    }

    $data = json_decode($raw, true);
    if (!is_array($data)) {
        out([], 'JSON inválido', false, 400);
    }

    return $data;
}

/**
 * Proyección mínima de una solicitud para exponerla al agente (sin datos sensibles).
 */
function proyeccionEstado(array $req): array
{
    return [
        'guid'       => $req['guid'] ?? null,
        'status'     => $req['status'] ?? null,
        'direccion'  => $req['correo']['direccion'] ?? null,
        'expires_at' => $req['expires_at'] ?? null,
    ];
}

/**
 * Construye el EmailProvisioner con la misma configuración que run_provisioning.php.
 */
function construirProvisioner(): EmailProvisioner
{
    $logger = new Logger(__DIR__ . '/logs/email-provision.log');
    $repository = new RequestRepository(LI_REQUESTS_FILE);
    $cpanel = CPanelClient::fromConfig();
    $mailer = MailSender::fromConfig();

    return new EmailProvisioner(
        $cpanel,
        $mailer,
        $repository,
        $logger,
        new UsernameGenerator(),
        new PasswordGenerator(),
        Config::get('CPANEL_DOMAIN', 'chiledao.cl'),
        Config::getInt('CPANEL_QUOTA_MB', 250),
        Config::get('WEBMAIL_URL', 'https://webmail.chiledao.cl')
    );
}

/**
 * Elimina una casilla de correo en cPanel vía UAPI Email::delete_pop.
 * CPanelClient no trae este método (solo add_pop/list_pops), así que se
 * replica aquí el mismo patrón de llamada que usa CPanelClient::addPop().
 */
function eliminarCasillaCpanel(CPanelClient $cpanel, string $domain, string $localPart): void
{
    $cpanel->call('Email', 'delete_pop', [
        'domain' => $domain,
        'email'  => $localPart,
    ]);
}

/**
 * Envía un correo de texto plano usando mail() nativo, con los mismos headers
 * que MailSender::enviarCredenciales() (MailSender no expone un método genérico,
 * así que se replica aquí el mismo patrón en vez de tocar ese módulo).
 */
function enviarCorreoTexto(string $destinatario, string $asunto, string $cuerpo): bool
{
    $fromAddress = Config::get('MAIL_FROM', 'soporte@chiledao.cl');
    $fromName = Config::get('MAIL_FROM_NAME', 'Los Inmortales');

    $headers = [
        'MIME-Version: 1.0',
        'Content-Type: text/plain; charset=UTF-8',
        'From: ' . $fromName . ' <' . $fromAddress . '>',
        'Reply-To: ' . $fromAddress,
        'X-Mailer: LosInmortales-EmailProvisioner',
    ];

    return mail($destinatario, $asunto, $cuerpo, implode("\r\n", $headers));
}

// --- Ruteo -------------------------------------------------------------------

$action = $_GET['action'] ?? 'ping';

try {
    switch ($action) {

        case 'ping':
            out(["status" => "online"]);
            break;

        case 'crear': {
            $body = leerBodyJson();

            $email = trim($body['email'] ?? '');
            $nombre = trim($body['nombre'] ?? '');
            $centros = $body['centros'] ?? null;
            $periodo = trim($body['periodo'] ?? '');
            $mandatoTexto = trim($body['mandato_texto'] ?? '');
            $firma = trim($body['firma'] ?? '');

            if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
                out([], 'email inválido', false, 400);
            }
            if ($nombre === '') {
                out([], 'nombre no puede estar vacío', false, 400);
            }
            if (!is_array($centros) || count($centros) === 0) {
                out([], 'centros debe ser un arreglo no vacío', false, 400);
            }
            if ($mandatoTexto === '' || $firma === '') {
                out([], 'mandato_texto y firma son obligatorios', false, 400);
            }

            $ip = $_SERVER['REMOTE_ADDR'] ?? 'desconocida';

            $entry = li_create_request($email, $ip);

            // Detalle mínimo: sin run, sin teléfono, sin cédula (no aplica en este flujo de agente).
            $detalle = [
                'nombre'   => $nombre,
                'run'      => null,
                'telefono' => null,
                'cedula'   => 'no aplica',
                'centros'  => array_values($centros),
                'periodo'  => $periodo,
            ];

            $mandato = [
                'texto'       => $mandatoTexto,
                'firma'       => $firma,
                'firmado_en'  => date('Y-m-d H:i:s'),
                'ip'          => $ip,
            ];

            li_complete_request($entry['guid'], $detalle, $mandato);

            // status queda en 'en_gestion' tras li_complete_request.
            out(['guid' => $entry['guid'], 'status' => 'en_gestion']);
            break;
        }

        case 'provisionar': {
            $body = leerBodyJson();
            $guid = $body['guid'] ?? '';

            if (!esGuidValido($guid)) {
                out([], 'guid inválido', false, 400);
            }

            $request = li_find_by_guid($guid);
            if (!$request) {
                out([], 'Solicitud no encontrada', false, 404);
            }

            // Idempotente: si ya tiene casilla creada, se devuelve tal cual.
            if (isset($request['correo']['direccion'])) {
                out([
                    'guid'      => $guid,
                    'status'    => $request['status'] ?? 'correo_creado',
                    'direccion' => $request['correo']['direccion'],
                ]);
            }

            if (($request['status'] ?? '') !== 'en_gestion') {
                out([], 'La solicitud no está en estado en_gestion', false, 409);
            }

            $provisioner = construirProvisioner();
            $resultado = $provisioner->procesar($request);

            $actualizada = li_find_by_guid($guid);

            if (!$resultado || !isset($actualizada['correo']['direccion'])) {
                // El motivo real (credenciales de cPanel, envio de correo, cuota) se devuelve
                // tal como lo dejo el provisioner: sin esto, diagnosticar exige leer los logs
                // del servidor por FTP.
                out(
                    [
                        'guid'    => $guid,
                        'status'  => $actualizada['status'] ?? 'error_correo',
                        'detalle' => $actualizada['correo_error'] ?? 'sin detalle registrado',
                    ],
                    'No se pudo aprovisionar la casilla',
                    false,
                    500
                );
            }

            out([
                'guid'      => $guid,
                'status'    => $actualizada['status'],
                'direccion' => $actualizada['correo']['direccion'],
            ]);
            break;
        }

        case 'estado': {
            $guid = $_GET['guid'] ?? '';

            if (!esGuidValido($guid)) {
                out([], 'guid inválido', false, 400);
            }

            $request = li_find_by_guid($guid);
            if (!$request) {
                out([], 'Solicitud no encontrada', false, 404);
            }

            out(proyeccionEstado($request));
            break;
        }

        case 'eliminar': {
            $body = leerBodyJson();
            $guid = $body['guid'] ?? '';

            if (!esGuidValido($guid)) {
                out([], 'guid inválido', false, 400);
            }

            $request = li_find_by_guid($guid);
            if (!$request) {
                out([], 'Solicitud no encontrada', false, 404);
            }

            // Si llegó a tener casilla en cPanel, se borra primero allá.
            $localPart = $request['correo']['usuario'] ?? null;
            if ($localPart) {
                $domain = Config::get('CPANEL_DOMAIN', 'chiledao.cl');
                $cpanel = CPanelClient::fromConfig();
                eliminarCasillaCpanel($cpanel, $domain, basename((string)$localPart));
            }

            // Elimina el archivo de cédula asociado, si existiera (patrón de cleanup.php).
            $cedulaNombre = $request['mandato']['cedula_path'] ?? null;
            if ($cedulaNombre) {
                $rutaCedula = LI_CEDULAS_DIR . '/' . basename((string)$cedulaNombre);
                if (is_file($rutaCedula)) {
                    unlink($rutaCedula);
                }
            }

            // Elimina el registro completo del store (igual que cleanup.php: se reescribe sin él).
            $todas = li_read_all();
            $restantes = array_values(array_filter($todas, function ($r) use ($guid) {
                return ($r['guid'] ?? null) !== $guid;
            }));
            li_write_all($restantes);

            out(['guid' => $guid, 'borrado' => true]);
            break;
        }

        case 'notificar': {
            $body = leerBodyJson();

            $email = trim($body['email'] ?? '');
            $tipo = trim($body['tipo'] ?? '');
            $datos = $body['datos'] ?? [];

            if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
                out([], 'email inválido', false, 400);
            }
            if (!is_array($datos)) {
                out([], 'datos debe ser un objeto', false, 400);
            }

            if ($tipo === 'codigo') {
                $codigo = trim((string)($datos['codigo'] ?? ''));
                if (!preg_match('/^\d{6}$/', $codigo)) {
                    out([], 'datos.codigo debe ser un código de 6 dígitos', false, 400);
                }

                $asunto = 'Código de verificación para la firma de tu mandato';
                $cuerpo = <<<TEXT
Hola,

Tu código de verificación para firmar el mandato en Los Inmortales es:

    {$codigo}

Este código es de un solo uso. Si no solicitaste esta firma, ignora este correo.

— Equipo Los Inmortales
TEXT;

                $enviado = enviarCorreoTexto($email, $asunto, $cuerpo);
                out(['enviado' => $enviado]);
                break;
            }

            if ($tipo === 'acuerdo') {
                $texto = trim((string)($datos['texto'] ?? ''));
                if ($texto === '') {
                    out([], 'datos.texto no puede estar vacío', false, 400);
                }
                if (strlen($texto) > 12 * 1024) {
                    out([], 'datos.texto supera el máximo permitido (12KB)', false, 400);
                }

                $fechaHora = date('Y-m-d H:i:s');
                $asunto = 'Copia del acuerdo firmado — Los Inmortales';
                $cuerpo = <<<TEXT
Hola,

Adjuntamos la copia del acuerdo (mandato) que firmaste el {$fechaHora}.

--------------------------------------------------------------------
{$texto}
--------------------------------------------------------------------

Conserva este correo como respaldo de la firma.

— Equipo Los Inmortales
TEXT;

                $enviado = enviarCorreoTexto($email, $asunto, $cuerpo);
                out(['enviado' => $enviado]);
                break;
            }

            out([], "tipo debe ser 'codigo' o 'acuerdo'", false, 400);
            break;
        }

        case 'correos': {
            if (!function_exists('imap_open')) {
                out([], 'La extensión imap de PHP no está disponible en este servidor', false, 501);
            }

            $casilla = $_GET['casilla'] ?? '';
            if (!is_string($casilla) || !preg_match('/^[a-z0-9._-]+$/', $casilla)) {
                out([], 'casilla inválida', false, 400);
            }

            // Ubica la solicitud que tiene esta casilla asignada, para recuperar su password.
            $request = null;
            foreach (li_read_all() as $req) {
                if (($req['correo']['usuario'] ?? null) === $casilla) {
                    $request = $req;
                    break;
                }
            }
            if (!$request) {
                out([], 'No existe una casilla asignada con ese nombre de usuario', false, 404);
            }

            $password = $request['correo']['password_temporal'] ?? null;
            if (!$password) {
                out([], 'La casilla no tiene credenciales registradas', false, 404);
            }

            $domain = Config::get('CPANEL_DOMAIN', 'chiledao.cl');
            $direccionCompleta = $casilla . '@' . $domain;
            $mailbox = '{mail.chiledao.cl:993/imap/ssl}INBOX';

            $conexion = @imap_open($mailbox, $direccionCompleta, (string)$password, OP_READONLY, 1);
            if ($conexion === false) {
                $detalleImap = imap_last_error();
                error_log('[api_agente] imap_open falló para ' . $casilla . ': ' . $detalleImap);
                out([], 'No se pudo conectar a la casilla de correo', false, 502);
            }

            $total = imap_num_msg($conexion);
            $mensajes = [];

            // Los últimos 10, del más reciente al más antiguo.
            $inicio = max(1, $total - 9);
            for ($i = $total; $i >= $inicio; $i--) {
                $overview = imap_fetch_overview($conexion, (string)$i, 0);
                $cabecera = $overview[0] ?? null;

                $estructura = imap_fetchstructure($conexion, $i);
                $adjuntos = [];
                if ($estructura && isset($estructura->parts) && is_array($estructura->parts)) {
                    foreach ($estructura->parts as $indiceParte => $parte) {
                        $nombreAdjunto = null;
                        if (isset($parte->dparameters)) {
                            foreach ($parte->dparameters as $param) {
                                if (strtolower($param->attribute) === 'filename') {
                                    $nombreAdjunto = $param->value;
                                }
                            }
                        }
                        if (!$nombreAdjunto && isset($parte->parameters)) {
                            foreach ($parte->parameters as $param) {
                                if (strtolower($param->attribute) === 'name') {
                                    $nombreAdjunto = $param->value;
                                }
                            }
                        }
                        if ($nombreAdjunto) {
                            $adjuntos[] = $nombreAdjunto;
                        }
                    }
                }

                $textoPlano = @imap_fetchbody($conexion, $i, '1');
                if (!is_string($textoPlano) || $textoPlano === '') {
                    $textoPlano = @imap_body($conexion, $i) ?: '';
                }
                // Decodifica quoted-printable/base64 de forma best-effort antes de recortar.
                $textoPlano = quoted_printable_decode($textoPlano);

                $mensajes[] = [
                    'de'       => $cabecera->from ?? null,
                    'asunto'   => isset($cabecera->subject) ? imap_utf8($cabecera->subject) : null,
                    'fecha'    => $cabecera->date ?? null,
                    'texto'    => mb_substr($textoPlano, 0, 2000),
                    'adjuntos' => $adjuntos,
                ];
            }

            imap_close($conexion);

            out(['casilla' => $direccionCompleta, 'mensajes' => $mensajes]);
            break;
        }

        default:
            out([], 'Acción no implementada', false, 501);
    }
} catch (\Throwable $e) {
    fail500($e);
}
