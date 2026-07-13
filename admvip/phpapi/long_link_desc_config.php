<?php
// KOKO_LONG_LINK_DESC_CONFIG_V2
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
        $v = trim($v, "\"'");
        $out[$k] = $v;
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

$key = 'kami_long_link_desc_template';
$defaultDesc = '';

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
        $stmt = $pdo->prepare("SELECT setting_value FROM system_settings WHERE setting_key=? LIMIT 1");
        $stmt->execute([$key]);
        $row = $stmt->fetch();

        $desc = $row ? (string)$row['setting_value'] : $defaultDesc;

        // 兼容前端不同版本可能读取的字段名
        koko_json([
            'success' => true,
            'desc' => $desc,
            'long_link_desc' => $desc,
            'long_link_desc_template' => $desc,
            'data' => [
                'desc' => $desc,
                'long_link_desc' => $desc,
                'long_link_desc_template' => $desc,
            ],
        ]);
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $raw = file_get_contents('php://input');
        $data = json_decode($raw, true);
        if (!is_array($data)) $data = $_POST;

        $desc = '';

        foreach (['desc', 'long_link_desc', 'long_link_desc_template', 'template', 'value'] as $k) {
            if (isset($data[$k])) {
                $desc = (string)$data[$k];
                break;
            }
        }

        if (mb_strlen($desc, 'UTF-8') > 5000) {
            $desc = mb_substr($desc, 0, 5000, 'UTF-8');
        }

        $stmt = $pdo->prepare("
            INSERT INTO system_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, NOW())
            ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value), updated_at=NOW()
        ");
        $stmt->execute([$key, $desc]);

        koko_json([
            'success' => true,
            'message' => '长链接说明模板保存成功',
            'desc' => $desc,
            'data' => [
                'desc' => $desc,
                'long_link_desc' => $desc,
                'long_link_desc_template' => $desc,
            ],
        ]);
    }

    koko_json(['success' => false, 'message' => 'Method Not Allowed'], 405);

} catch (Throwable $e) {
    error_log('long_link_desc_config failed: ' . $e->getMessage());
    koko_json(['success' => false, 'message' => '服务器错误：' . $e->getMessage()], 500);
}
