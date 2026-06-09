<?php
header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/../lib/config.php';

koko_require_admin_token(false);

$defaults = koko_default_settings();
$allowedKeys = array_keys($defaults);

try {
    $pdo = koko_pdo();
    koko_ensure_system_settings($pdo);

    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $placeholders = implode(',', array_fill(0, count($allowedKeys), '?'));
        $stmt = $pdo->prepare("SELECT setting_key, setting_value FROM system_settings WHERE setting_key IN ($placeholders)");
        $stmt->execute($allowedKeys);
        $settings = $defaults;
        foreach ($stmt->fetchAll() as $row) {
            $settings[$row['setting_key']] = (string)$row['setting_value'];
        }
        echo json_encode(['success' => true, 'settings' => $settings], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }

    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        http_response_code(405);
        echo json_encode(['success' => false, 'message' => '请求方法不支持'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $data = json_decode(file_get_contents('php://input'), true);
    if (!is_array($data)) {
        throw new InvalidArgumentException('请求 JSON 无效');
    }

    $redeemUrl = trim((string)($data['redeem_url'] ?? ''));
    if ($redeemUrl === '' || filter_var($redeemUrl, FILTER_VALIDATE_URL) === false || !in_array(strtolower((string)parse_url($redeemUrl, PHP_URL_SCHEME)), ['http', 'https'], true)) {
        throw new InvalidArgumentException('兑换链接必须是有效的 HTTP/HTTPS 地址');
    }

    $settings = ['redeem_url' => $redeemUrl];
    foreach (['notify_device_offline', 'notify_new_recharge_task', 'notify_backend_error'] as $key) {
        $value = $data[$key] ?? null;
        if (!in_array($value, [0, 1, '0', '1'], true)) {
            throw new InvalidArgumentException($key . ' 只能为 0 或 1');
        }
        $settings[$key] = (string)$value;
    }

    $stmt = $pdo->prepare('INSERT INTO system_settings (setting_key, setting_value) VALUES (?, ?) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)');
    $pdo->beginTransaction();
    foreach ($settings as $key => $value) {
        $stmt->execute([$key, $value]);
    }
    $pdo->commit();

    echo json_encode(['success' => true, 'message' => '保存成功'], JSON_UNESCAPED_UNICODE);
} catch (InvalidArgumentException $e) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => $e->getMessage()], JSON_UNESCAPED_UNICODE);
} catch (Exception $e) {
    if (isset($pdo) && $pdo->inTransaction()) {
        $pdo->rollBack();
    }
    error_log('system_settings.php failed: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => '服务器内部错误'], JSON_UNESCAPED_UNICODE);
}
