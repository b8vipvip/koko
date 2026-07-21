<?php
require_once __DIR__ . '/../lib/config.php';

header('Content-Type: application/json; charset=utf-8');
koko_require_admin_token(false);

function koko_system_setting_keys() {
    return [
        'redeem_url',
        'notify_device_offline',
        'notify_new_recharge_task',
        'notify_backend_error',
        'usrvip_site_schedule_enabled',
        'usrvip_site_close_time',
        'usrvip_site_open_time',
        'usrvip_site_closed_message',
        'wecom_corp_id',
        'wecom_agent_secret',
        'wecom_agent_id',
        'wecom_to_user',
        'wecom_to_party',
        'wecom_to_tag',
    ];
}

function koko_validate_hhmm($value, $field) {
    $value = trim((string)$value);
    if (!preg_match('/^\d{2}:\d{2}$/', $value)) {
        throw new InvalidArgumentException($field . ' 必须为 HH:MM');
    }
    [$hh, $mm] = array_map('intval', explode(':', $value));
    if ($hh > 23 || $mm > 59) {
        throw new InvalidArgumentException($field . ' 必须为 HH:MM');
    }
    return $value;
}

try {
    $pdo = koko_pdo();
    koko_ensure_system_settings($pdo);

    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $stmt = $pdo->prepare('SELECT setting_key, setting_value FROM system_settings WHERE setting_key = ? LIMIT 1');
        $settings = [];
        foreach (koko_system_setting_keys() as $key) {
            $stmt->execute([$key]);
            $value = $stmt->fetchColumn();
            $settings[$key] = $value === false || $value === null ? (koko_default_settings()[$key] ?? '') : (string)$value;
        }

        // Secret 只允许写入，不回传到浏览器，避免后台页面或网络响应泄露。
        $settings['wecom_agent_secret_configured'] = trim((string)$settings['wecom_agent_secret']) !== '';
        $settings['wecom_agent_secret'] = '';
        $settings['wecom_configured'] = (
            trim((string)$settings['wecom_corp_id']) !== ''
            && $settings['wecom_agent_secret_configured']
            && (int)$settings['wecom_agent_id'] > 0
            && (
                trim((string)$settings['wecom_to_user']) !== ''
                || trim((string)$settings['wecom_to_party']) !== ''
                || trim((string)$settings['wecom_to_tag']) !== ''
            )
        );

        echo json_encode(['success' => true, 'settings' => $settings], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }

    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        http_response_code(405);
        echo json_encode(['success' => false, 'message' => 'Method not allowed'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $payload = json_decode(file_get_contents('php://input'), true);
    if (!is_array($payload) && !empty($_POST)) {
        $payload = $_POST;
    }
    if (!is_array($payload)) {
        throw new InvalidArgumentException('请求 JSON 无效');
    }

    $values = [];
    foreach (koko_system_setting_keys() as $key) {
        if (!array_key_exists($key, $payload)) {
            continue;
        }
        $value = $payload[$key];
        if (in_array($key, ['notify_device_offline', 'notify_new_recharge_task', 'notify_backend_error', 'usrvip_site_schedule_enabled'], true)) {
            $value = ((string)$value === '1' || $value === 1 || $value === true) ? '1' : '0';
        } elseif (in_array($key, ['usrvip_site_close_time', 'usrvip_site_open_time'], true)) {
            $value = koko_validate_hhmm($value, $key);
        } elseif ($key === 'wecom_agent_id') {
            $value = trim((string)$value);
            if ($value !== '' && (!ctype_digit($value) || (int)$value <= 0)) {
                throw new InvalidArgumentException('企业微信 AgentId 必须为正整数');
            }
        } else {
            $value = trim((string)$value);
        }

        // Secret 留空代表保持原值，避免编辑其它配置时清空密钥。
        if ($key === 'wecom_agent_secret' && $value === '') {
            continue;
        }
        $values[$key] = $value;
    }

    $stmt = $pdo->prepare(
        'INSERT INTO system_settings (setting_key, setting_value, updated_at) VALUES (?, ?, NOW())
         ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), updated_at = NOW()'
    );
    foreach ($values as $key => $value) {
        $stmt->execute([$key, $value]);
    }

    echo json_encode(['success' => true, 'message' => '保存成功'], JSON_UNESCAPED_UNICODE);
} catch (Throwable $e) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => $e->getMessage()], JSON_UNESCAPED_UNICODE);
}
