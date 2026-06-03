<?php
require_once __DIR__ . '/config.php';
require_once dirname(__DIR__) . '/vendor/autoload.php';

use PHPMailer\PHPMailer\PHPMailer;

if (!function_exists('koko_mail_config')) {
    function koko_mail_config() {
        return array(
            'host' => koko_env('SMTP_HOST', 'smtp.example.com'),
            'port' => (int)koko_env('SMTP_PORT', '465'),
            'username' => koko_env('SMTP_USERNAME', ''),
            'password' => koko_env('SMTP_PASSWORD', ''),
            'encryption' => strtolower(koko_env('SMTP_ENCRYPTION', 'ssl')),
            'from' => koko_env('MAIL_FROM', 'noreply@example.com'),
            'from_name' => koko_env('MAIL_FROM_NAME', 'Koko'),
            'to' => koko_env('MAIL_TO', 'admin@example.com'),
            'to_name' => koko_env('MAIL_TO_NAME', 'Admin'),
        );
    }
}

if (!function_exists('koko_create_mailer')) {
    function koko_create_mailer() {
        $cfg = koko_mail_config();
        $mail = new PHPMailer(true);
        $mail->isSMTP();
        $mail->Host = $cfg['host'];
        $mail->SMTPAuth = true;
        $mail->Username = $cfg['username'];
        $mail->Password = $cfg['password'];
        if ($cfg['encryption'] === 'ssl' || $cfg['encryption'] === 'smtps') {
            $mail->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS;
        } elseif ($cfg['encryption'] === 'tls' || $cfg['encryption'] === 'starttls') {
            $mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS;
        } else {
            $mail->SMTPSecure = false;
        }
        $mail->Port = $cfg['port'];
        $mail->CharSet = 'UTF-8';
        $mail->setFrom($cfg['from'], $cfg['from_name']);
        $mail->addAddress($cfg['to'], $cfg['to_name']);
        return $mail;
    }
}
