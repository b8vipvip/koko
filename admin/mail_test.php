<?php
require_once __DIR__ . '/vendor/autoload.php';

$mail = new \PHPMailer\PHPMailer\PHPMailer(true);

try {
    $mail->isSMTP();
    $mail->Host = 'smtp.qq.com';
    $mail->SMTPAuth = true;
    $mail->Username = '3891327165@qq.com';
    $mail->Password = 'orrr';
    $mail->SMTPSecure = \PHPMailer\PHPMailer\PHPMailer::ENCRYPTION_SMTPS;
    $mail->Port = 465;
    $mail->CharSet = 'UTF-8';

    $mail->setFrom('3891327165@qq.com', '任务提醒');
    $mail->addAddress('3959418301@qq.com', '管理员');

    $mail->Subject = '邮件测试';
    $mail->Body = '这是一封测试邮件';

    $mail->send();
    echo "邮件发送成功";
} catch (Exception $e) {
    echo "邮件发送失败：" . $mail->ErrorInfo;
}