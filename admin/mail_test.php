<?php
require_once __DIR__ . '/lib/mailer.php';

try {
    koko_require_admin();
    $mail = koko_create_mailer();
    $mail->Subject = '邮件测试';
    $mail->Body = '这是一封测试邮件';
    $mail->send();
    echo '邮件发送成功';
} catch (Throwable $e) {
    error_log('测试邮件发送失败: ' . $e->getMessage());
    echo '邮件发送失败';
}
