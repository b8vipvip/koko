<?php
require_once __DIR__ . '/lib/config.php';

try {
    $pdo = koko_pdo();
} catch (Throwable $e) {
    error_log('PDO 数据库连接失败: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'db_error'], JSON_UNESCAPED_UNICODE);
    exit;
}
?>
