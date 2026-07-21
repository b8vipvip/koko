<?php
require_once __DIR__ . '/lib/mailer.php';

try {
    koko_require_admin_token(false);
    koko_send_wecom_text('企业微信测试通知', '这是一条来自 Koko 管理后台的企业微信测试通知。');
    echo "企业微信通知发送成功";
} catch (Throwable $e) {
    http_response_code(500);
    echo "企业微信通知发送失败：" . $e->getMessage();
}
