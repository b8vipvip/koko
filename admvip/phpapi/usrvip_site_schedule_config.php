<?php
header('Content-Type: application/json; charset=utf-8');

function koko_json($arr, $code = 200) {
    http_response_code($code);
    echo json_encode($arr, JSON_UNESCAPED_UNICODE);
    exit;
}

function read_env_file($path) {
    $out = [];
    if (!is_file($path)) return $out;
    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') continue;
        $pos = strpos($line, '=');
        if ($pos === false) continue;
        $k = trim(substr($line, 0, $pos));
        $v = trim(substr($line, $pos + 1));
        $out[$k] = trim($v, "\"'");
    }
    return $out;
}

$env = array_merge(
    read_env_file('/opt/koko/.env'),
    read_env_file('/opt/koko/server/.env')
);

$host = $env['DB_HOST'] ?? $env['MYSQL_HOST'] ?? '127.0.0.1';
$db   = $env['DB_NAME'] ?? $env['MYSQL_DATABASE'] ?? $env['MYSQL_DB'] ?? 'kugo';
$user = $env['DB_USER'] ?? $env['MYSQL_USER'] ?? 'kugo';
$pass = $env['DB_PASSWORD'] ?? $env['MYSQL_PASSWORD'] ?? $env['DB_PASS'] ?? $env['MYSQL_PASS'] ?? '';
$port = $env['DB_PORT'] ?? $env['MYSQL_PORT'] ?? '3306';

$defaults = [
    'usrvip_site_schedule_enabled' => '0',
    'usrvip_site_close_time' => '23:00',
    'usrvip_site_open_time' => '08:00',
    'usrvip_site_closed_message' => '当前站点维护中，请稍后再试',
];

try {
    $pdo = new PDO(
        "mysql:host=$host;port=$port;dbname=$db;charset=utf8mb4",
        $user,
        $pass,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );

    $pdo->exec("
        CREATE TABLE IF NOT EXISTS system_settings (
          setting_key varchar(100) NOT NULL,
          setting_value text,
          updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (setting_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");

    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $result = $defaults;

        $keys = array_keys($defaults);
        $placeholders = implode(',', array_fill(0, count($keys), '?'));

        $stmt = $pdo->prepare("SELECT setting_key, setting_value FROM system_settings WHERE setting_key IN ($placeholders)");
        $stmt->execute($keys);

        foreach ($stmt->fetchAll() as $row) {
            $result[$row['setting_key']] = $row['setting_value'];
        }

        koko_json([
            'success' => true,
            'data' => $result,
        ]);
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $raw = file_get_contents('php://input');
        $data = json_decode($raw, true);
        if (!is_array($data)) $data = $_POST;

        $enabled = !empty($data['usrvip_site_schedule_enabled']) ? '1' : '0';
        $closeTime = trim((string)($data['usrvip_site_close_time'] ?? '23:00'));
        $openTime = trim((string)($data['usrvip_site_open_time'] ?? '08:00'));
        $message = trim((string)($data['usrvip_site_closed_message'] ?? ''));

        if (!preg_match('/^\d{2}:\d{2}$/', $closeTime)) {
            koko_json(['success' => false, 'message' => '关闭时间格式必须是 HH:MM'], 400);
        }

        if (!preg_match('/^\d{2}:\d{2}$/', $openTime)) {
            koko_json(['success' => false, 'message' => '开启时间格式必须是 HH:MM'], 400);
        }

        $save = [
            'usrvip_site_schedule_enabled' => $enabled,
            'usrvip_site_close_time' => $closeTime,
            'usrvip_site_open_time' => $openTime,
            'usrvip_site_closed_message' => mb_substr($message, 0, 1000, 'UTF-8'),
        ];

        $stmt = $pdo->prepare("
            INSERT INTO system_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, NOW())
            ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value), updated_at=NOW()
        ");

        foreach ($save as $k => $v) {
            $stmt->execute([$k, $v]);
        }

        koko_json([
            'success' => true,
            'message' => '保存成功',
            'data' => $save,
        ]);
    }

    koko_json(['success' => false, 'message' => 'Method Not Allowed'], 405);

} catch (Throwable $e) {
    error_log('usrvip_site_schedule_config failed: ' . $e->getMessage());
    koko_json(['success' => false, 'message' => '服务器错误：' . $e->getMessage()], 500);
}
