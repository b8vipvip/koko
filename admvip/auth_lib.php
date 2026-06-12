<?php
// KOKO_AUTH_LIB_NOOP_NGINX_KEY_V1
// PHP 登录验证已停用，后台访问由 Nginx key + Cookie 保护。
// 这个文件只保留兼容函数，避免旧页面 require/auth 检查时报错。

if (session_status() === PHP_SESSION_NONE) {
    @session_start();
}

if (!function_exists('is_logged_in')) {
    function is_logged_in() { return true; }
}

if (!function_exists('is_admin')) {
    function is_admin() { return true; }
}

if (!function_exists('require_login')) {
    function require_login() { return true; }
}

if (!function_exists('require_admin')) {
    function require_admin() { return true; }
}

if (!function_exists('check_login')) {
    function check_login() { return true; }
}

if (!function_exists('check_admin')) {
    function check_admin() { return true; }
}

if (!function_exists('admin_required')) {
    function admin_required() { return true; }
}

if (!function_exists('auth_required')) {
    function auth_required() { return true; }
}

if (!function_exists('get_current_user')) {
    function get_current_user() {
        return [
            'id' => 1,
            'username' => 'nginx_key_admin',
            'role' => 'admin'
        ];
    }
}

$_SESSION['admin_logged_in'] = true;
$_SESSION['username'] = 'nginx_key_admin';
$_SESSION['role'] = 'admin';
