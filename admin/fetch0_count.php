<?php
header('Content-Type: application/json; charset=utf-8');

// 你项目里如果有统一的数据库连接文件，就 require 一下（按你的实际路径改）
// require_once __DIR__ . '/DbClass.php'; 或 conn.php 等

// 示例：PDO 连接（把下面改成你自己的）

$host = 'localhost';
$db   = 'kugo';
$user = 'kugo';
$pass = 'HP77CyRpMxd8hhFN';
$charset = 'utf8mb4';

try {
    $dsn = "mysql:host=$host;dbname=$db;charset=$charset";
    $pdo = new PDO($dsn, $user, $pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);

    $stmt = $pdo->query("SELECT COUNT(*) AS c FROM code_data WHERE fetch_status = 0");
    $row = $stmt->fetch();
    echo json_encode(['count' => intval($row['c'] ?? 0)], JSON_UNESCAPED_UNICODE);

} catch (Throwable $e) {
    http_response_code(500);
    echo json_encode(['count' => 0, 'error' => 'db_error'], JSON_UNESCAPED_UNICODE);
}
