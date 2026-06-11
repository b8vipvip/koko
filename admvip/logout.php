<?php
require_once __DIR__ . '/auth_lib.php';

$cfg = koko_auth_config();
$name = $cfg['cookie_name'] ?? 'koko_admin_auth';

setcookie($name, '', [
    'expires' => time() - 3600,
    'path' => '/',
    'secure' => (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off'),
    'httponly' => true,
    'samesite' => 'Lax',
]);

header('Location: /login.php');
exit;
