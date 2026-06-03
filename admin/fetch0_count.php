<?php
header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/db.php';

try {
    $stmt = $pdo->query("SELECT COUNT(*) AS c FROM code_data WHERE fetch_status = 0");
    $row = $stmt->fetch();
    echo json_encode(['count' => intval($row['c'] ?? 0)], JSON_UNESCAPED_UNICODE);
} catch (Throwable $e) {
    error_log('fetch0_count 查询失败: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['count' => 0, 'error' => 'db_error'], JSON_UNESCAPED_UNICODE);
}
