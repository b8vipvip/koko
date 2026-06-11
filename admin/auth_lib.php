<?php
function koko_auth_config() {
    $file = '/opt/koko/koko_login_auth.php';
    if (!is_readable($file)) {
        return null;
    }

    $cfg = require $file;
    if (!is_array($cfg)) {
        return null;
    }

    return $cfg;
}

function koko_auth_is_logged_in() {
    $cfg = koko_auth_config();
    if (!$cfg) return false;

    $name = $cfg['cookie_name'] ?? 'koko_admin_auth';
    $value = $cfg['cookie_value'] ?? '';

    return isset($_COOKIE[$name]) && hash_equals((string)$value, (string)$_COOKIE[$name]);
}

function koko_auth_require_login() {
    if (!koko_auth_is_logged_in()) {
        header('Location: /login.php');
        exit;
    }
}
