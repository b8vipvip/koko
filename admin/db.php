<?php
require_once __DIR__ . '/lib/config.php';

try {
    $pdo = koko_pdo();
} catch (Exception $e) {
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['error' => 'db_error'], JSON_UNESCAPED_UNICODE);
    error_log('PDO connection failed: ' . $e->getMessage());
    exit;
}
?>
