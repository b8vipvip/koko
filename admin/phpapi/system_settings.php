<?php
// KOKO_SYSTEM_SETTINGS_NO_REDEEM_V9
// 系统配置页只负责邮件通知开关。
// 兑换链接已移动到 /kami.html，由 retail_exchange_url / agent_exchange_url 管理。
// 本接口不再读取、校验、保存 redeem_url。

header('Content-Type: application/json; charset=utf-8');

$host = '127.0.0.1';
$db   = 'kugo';
$user = 'kugo';
$pass = 'HP77CyRpMxd8hhFN';
$charset = 'utf8mb4';

function koko_json($arr, $code = 200) {
    http_response_code($code);
    echo json_encode($arr, JSON_UNESCAPED_UNICODE);
    exit;
}

try {
    $pdo = new PDO(
        "mysql:host=$host;dbname=$db;charset=$charset",
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

    $defaults = [
        'notify_backend_error' => '1',
        'notify_device_offline' => '1',
        'notify_new_recharge_task' => '1',
    ];

    foreach ($defaults as $k => $v) {
        $stmt = $pdo->prepare("
            INSERT INTO system_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, NOW())
            ON DUPLICATE KEY UPDATE setting_value = setting_value
        ");
        $stmt->execute([$k, $v]);
    }

    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $keys = array_keys($defaults);
        $in = implode(',', array_fill(0, count($keys), '?'));

        $stmt = $pdo->prepare("SELECT setting_key, setting_value FROM system_settings WHERE setting_key IN ($in)");
        $stmt->execute($keys);

        $settings = $defaults;
        foreach ($stmt->fetchAll() as $row) {
            $settings[$row['setting_key']] = (string)$row['setting_value'];
        }

        koko_json([
            'success' => true,
            'status' => 'success',
            'data' => $settings,
            'settings' => $settings,
            'notify_backend_error' => (int)$settings['notify_backend_error'],
            'notify_device_offline' => (int)$settings['notify_device_offline'],
            'notify_new_recharge_task' => (int)$settings['notify_new_recharge_task'],
        ]);
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $raw = file_get_contents('php://input');
        $data = json_decode($raw, true);

        if (!is_array($data)) {
            $data = $_POST;
        }

        $allowed = [
            'notify_backend_error',
            'notify_device_offline',
            'notify_new_recharge_task',
        ];

        $pdo->beginTransaction();

        foreach ($allowed as $key) {
            if (!array_key_exists($key, $data)) {
                continue;
            }

            $val = $data[$key];
            $val = ($val === true || $val === 1 || $val === '1' || $val === 'on' || $val === 'true') ? '1' : '0';

            $stmt = $pdo->prepare("
                INSERT INTO system_settings (setting_key, setting_value, updated_at)
                VALUES (?, ?, NOW())
                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), updated_at = NOW()
            ");
            $stmt->execute([$key, $val]);
        }

        // 确保旧兑换链接 key 不会被系统配置页重新写入
        $pdo->prepare("DELETE FROM system_settings WHERE setting_key = 'redeem_url'")->execute();

        $pdo->commit();

        $stmt = $pdo->prepare("
            SELECT setting_key, setting_value
            FROM system_settings
            WHERE setting_key IN ('notify_backend_error','notify_device_offline','notify_new_recharge_task')
        ");
        $stmt->execute();

        $settings = $defaults;
        foreach ($stmt->fetchAll() as $row) {
            $settings[$row['setting_key']] = (string)$row['setting_value'];
        }

        koko_json([
            'success' => true,
            'status' => 'success',
            'message' => '系统配置保存成功',
            'data' => $settings,
            'settings' => $settings,
            'notify_backend_error' => (int)$settings['notify_backend_error'],
            'notify_device_offline' => (int)$settings['notify_device_offline'],
            'notify_new_recharge_task' => (int)$settings['notify_new_recharge_task'],
        ]);
    }

    koko_json([
        'success' => false,
        'message' => 'Method Not Allowed',
    ], 405);

} catch (Throwable $e) {
    if (isset($pdo) && $pdo->inTransaction()) {
        $pdo->rollBack();
    }

    error_log('system_settings.php failed: ' . $e->getMessage());

    koko_json([
        'success' => false,
        'message' => $e->getMessage(),
    ], 500);
}
?>
