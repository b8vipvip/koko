<?php
/**
 * Shared PHP configuration for the admin PHP endpoints.
 * Compatible with PHP 7.x/8.x and usable from both web and CLI scripts.
 */

if (!function_exists('koko_load_env_file')) {
    function koko_load_env_file($path) {
        if (!$path || !is_readable($path)) {
            return;
        }

        $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        if ($lines === false) {
            return;
        }

        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '' || strpos($line, '#') === 0 || strpos($line, '=') === false) {
                continue;
            }

            list($key, $value) = explode('=', $line, 2);
            $key = trim($key);
            $value = trim($value);
            if ($key === '') {
                continue;
            }

            if ((strlen($value) >= 2) && (($value[0] === '"' && substr($value, -1) === '"') || ($value[0] === "'" && substr($value, -1) === "'"))) {
                $value = substr($value, 1, -1);
            }

            if (getenv($key) === false) {
                putenv($key . '=' . $value);
                $_ENV[$key] = $value;
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

        $candidates = array_filter(array_unique(array(
            getenv('PHP_ENV_FILE') ?: null,
            '/opt/koko/.env',
            dirname(__DIR__, 2) . '/.env',
            dirname(__DIR__) . '/.env',
        )));

        foreach ($candidates as $path) {
            koko_load_env_file($path);
        }
    }
}

if (!function_exists('koko_env')) {
    function koko_env($key, $default = '') {
        koko_bootstrap_env();
        $value = getenv($key);
        if ($value === false && isset($_ENV[$key])) {
            $value = $_ENV[$key];
        }
        return ($value === false || $value === null || $value === '') ? $default : $value;
    }
}

if (!function_exists('koko_db_config')) {
    function koko_db_config() {
        return array(
            'host' => koko_env('DB_HOST', '127.0.0.1'),
            'port' => (int)koko_env('DB_PORT', '3306'),
            'user' => koko_env('DB_USER', 'koko'),
            'password' => koko_env('DB_PASSWORD', ''),
            'database' => koko_env('DB_NAME', 'kugo'),
            'charset' => koko_env('DB_CHARSET', 'utf8mb4'),
        );
    }
}

if (!function_exists('koko_pdo')) {
    function koko_pdo() {
        $cfg = koko_db_config();
        $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=%s', $cfg['host'], $cfg['port'], $cfg['database'], $cfg['charset']);
        return new PDO($dsn, $cfg['user'], $cfg['password'], array(
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ));
    }
}

if (!function_exists('koko_mysqli')) {
    function koko_mysqli() {
        $cfg = koko_db_config();
        $conn = new mysqli($cfg['host'], $cfg['user'], $cfg['password'], $cfg['database'], $cfg['port']);
        if ($conn->connect_error) {
            throw new RuntimeException('数据库连接失败');
        }
        $conn->set_charset($cfg['charset']);
        return $conn;
    }
}

if (!function_exists('koko_admin_auth_error')) {
    function koko_admin_auth_error() {
        if (php_sapi_name() === 'cli') {
            return null;
        }
        $expected = koko_env('ADMIN_API_TOKEN', '');
        $provided = '';
        if (isset($_SERVER['HTTP_X_ADMIN_TOKEN'])) {
            $provided = $_SERVER['HTTP_X_ADMIN_TOKEN'];
        }

        if ($expected === '') {
            error_log('ADMIN_API_TOKEN is not configured; rejecting PHP admin API request');
            return array(503, '管理员鉴权未配置');
        }
        if (!hash_equals($expected, $provided)) {
            return array(401, '管理员鉴权失败');
        }
        return null;
    }
}

if (!function_exists('koko_require_admin')) {
    function koko_require_admin() {
        $error = koko_admin_auth_error();
        if ($error === null) {
            return;
        }
        list($status, $message) = $error;
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(array('success' => false, 'message' => $message), JSON_UNESCAPED_UNICODE);
        exit;
    }
}
