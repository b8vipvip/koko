<?php
/**
 * Shared PHP configuration loader for admin backends.
 *
 * Reads configuration in this order:
 *   1. getenv()/$_ENV/$_SERVER
 *   2. PHP_ENV_FILE when set
 *   3. /opt/koko/.env
 *   4. project root .env
 *   5. safe placeholders without real secrets
 */

if (!function_exists('koko_load_env_file')) {
    function koko_load_env_file($path) {
        if (!$path || !is_readable($path) || !is_file($path)) {
            return;
        }

        $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        if ($lines === false) {
            return;
        }

        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '' || strpos($line, '#') === 0) {
                continue;
            }
            if (strpos($line, 'export ') === 0) {
                $line = trim(substr($line, 7));
            }
            $equalsPos = strpos($line, '=');
            if ($equalsPos === false) {
                continue;
            }

            $key = trim(substr($line, 0, $equalsPos));
            $value = trim(substr($line, $equalsPos + 1));
            if ($key === '' || preg_match('/^[A-Za-z_][A-Za-z0-9_]*$/', $key) !== 1) {
                continue;
            }

            if (strlen($value) >= 2) {
                $first = $value[0];
                $last = $value[strlen($value) - 1];
                if (($first === '"' && $last === '"') || ($first === "'" && $last === "'")) {
                    $value = substr($value, 1, -1);
                }
            }

            if (getenv($key) === false && !array_key_exists($key, $_ENV) && !array_key_exists($key, $_SERVER)) {
                $_ENV[$key] = $value;
                $_SERVER[$key] = $value;
                putenv($key . '=' . $value);
            }
        }
    }
}

if (!function_exists('koko_bootstrap_env')) {
    function koko_bootstrap_env() {
        static $loaded = false;
        if ($loaded) {
            return;
        }
        $loaded = true;

        $paths = [];
        $configuredPath = getenv('PHP_ENV_FILE');
        if ($configuredPath === false && isset($_ENV['PHP_ENV_FILE'])) {
            $configuredPath = $_ENV['PHP_ENV_FILE'];
        }
        if ($configuredPath) {
            $paths[] = $configuredPath;
        }
        $paths[] = '/opt/koko/.env';
        $paths[] = dirname(__DIR__, 2) . '/.env';

        foreach (array_unique($paths) as $path) {
            koko_load_env_file($path);
        }
    }
}

if (!function_exists('koko_env')) {
    function koko_env($key, $default = '') {
        koko_bootstrap_env();

        $value = getenv($key);
        if ($value !== false) {
            return $value;
        }
        if (isset($_ENV[$key])) {
            return $_ENV[$key];
        }
        if (isset($_SERVER[$key])) {
            return $_SERVER[$key];
        }
        return $default;
    }
}

if (!function_exists('koko_db_config')) {
    function koko_db_config() {
        return [
            'host' => koko_env('DB_HOST', '127.0.0.1'),
            'port' => (int)koko_env('DB_PORT', '3306'),
            'user' => koko_env('DB_USER', 'koko'),
            'password' => koko_env('DB_PASSWORD', ''),
            'name' => koko_env('DB_NAME', 'kugo'),
            'charset' => koko_env('DB_CHARSET', 'utf8mb4'),
        ];
    }
}

if (!function_exists('koko_pdo')) {
    function koko_pdo() {
        $cfg = koko_db_config();
        $dsn = sprintf(
            'mysql:host=%s;port=%d;dbname=%s;charset=%s',
            $cfg['host'],
            $cfg['port'],
            $cfg['name'],
            $cfg['charset']
        );
        return new PDO($dsn, $cfg['user'], $cfg['password'], [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]);
    }
}

if (!function_exists('koko_mysqli')) {
    function koko_mysqli() {
        $cfg = koko_db_config();
        $conn = new mysqli($cfg['host'], $cfg['user'], $cfg['password'], $cfg['name'], $cfg['port']);
        if (!$conn->connect_error) {
            $conn->set_charset($cfg['charset']);
        }
        return $conn;
    }
}

if (!function_exists('koko_mail_config')) {
    function koko_mail_config() {
        return [
            'host' => koko_env('SMTP_HOST', ''),
            'port' => (int)koko_env('SMTP_PORT', '465'),
            'username' => koko_env('SMTP_USERNAME', ''),
            'password' => koko_env('SMTP_PASSWORD', ''),
            'encryption' => strtolower(koko_env('SMTP_ENCRYPTION', 'ssl')),
            'from' => koko_env('MAIL_FROM', ''),
            'from_name' => koko_env('MAIL_FROM_NAME', 'Koko'),
            'to' => koko_env('MAIL_TO', ''),
            'to_name' => koko_env('MAIL_TO_NAME', 'Admin'),
        ];
    }
}

if (!function_exists('koko_admin_token')) {
    function koko_admin_token() {
        return trim((string)koko_env('ADMIN_API_TOKEN', ''));
    }
}

if (!function_exists('koko_request_header')) {
    function koko_request_header($name) {
        $serverKey = 'HTTP_' . strtoupper(str_replace('-', '_', $name));
        if (isset($_SERVER[$serverKey])) {
            return $_SERVER[$serverKey];
        }
        if (function_exists('getallheaders')) {
            $headers = getallheaders();
            foreach ($headers as $key => $value) {
                if (strcasecmp($key, $name) === 0) {
                    return $value;
                }
            }
        }
        return '';
    }
}

if (!function_exists('koko_require_admin_token')) {
    function koko_require_admin_token($allowCli = true) {
        if ($allowCli && PHP_SAPI === 'cli') {
            return;
        }

        $expected = koko_admin_token();
        if ($expected === '') {
            http_response_code(403);
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode(['success' => false, 'error' => 'ADMIN_API_TOKEN is not configured'], JSON_UNESCAPED_UNICODE);
            exit;
        }

        $provided = trim((string)koko_request_header('X-Admin-Token'));
        if ($provided === '' || !hash_equals($expected, $provided)) {
            http_response_code(401);
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode(['success' => false, 'error' => 'Invalid admin token'], JSON_UNESCAPED_UNICODE);
            exit;
        }
    }
}
