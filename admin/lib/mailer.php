<?php
require_once __DIR__ . '/config.php';
require_once dirname(__DIR__) . '/vendor/autoload.php';

use PHPMailer\PHPMailer\PHPMailer;

if (!function_exists('koko_create_mailer')) {
    function koko_create_mailer() {
        $cfg = koko_mail_config();

        foreach (['host', 'username', 'password', 'from', 'to'] as $key) {
            if (trim((string)$cfg[$key]) === '') {
                throw new RuntimeException('Mail configuration missing: ' . $key);
            }
        }

        $mail = new PHPMailer(true);
        $mail->isSMTP();
        $hostProperty = 'Host';
        $usernameProperty = 'Username';
        $passwordProperty = 'Password';
        $mail->{$hostProperty} = $cfg['host'];
        $mail->SMTPAuth = true;
        $mail->{$usernameProperty} = $cfg['username'];
        $mail->{$passwordProperty} = $cfg['password'];
        $mail->Port = $cfg['port'];
        $mail->CharSet = 'UTF-8';

        if ($cfg['encryption'] === 'ssl' || $cfg['encryption'] === 'smtps') {
            $mail->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS;
        } elseif ($cfg['encryption'] === 'tls' || $cfg['encryption'] === 'starttls') {
            $mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS;
        } elseif ($cfg['encryption'] === '' || $cfg['encryption'] === 'none') {
            $mail->SMTPSecure = false;
        } else {
            throw new RuntimeException('Unsupported SMTP_ENCRYPTION: ' . $cfg['encryption']);
        }

        $mail->setFrom($cfg['from'], $cfg['from_name']);
        $mail->addAddress($cfg['to'], $cfg['to_name']);

        return $mail;
    }
}
