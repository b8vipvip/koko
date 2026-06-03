<?php
header('Content-Type: application/json');
require_once '../db.php';

$data = json_decode(file_get_contents('php://input'), true);
$start_date = $data['start_date'];
$end_date = $data['end_date'];

try {
    $stmt = $pdo->prepare("
        SELECT
            SUM(fund_in) AS total_fund_in,
            SUM(manual_fund_out) AS total_manual_fund_out,
            SUM(auto_fund_out) AS total_auto_fund_out,
            (SUM(manual_fund_out) + SUM(auto_fund_out)) AS total_fund_out
        FROM device_fund_details
        WHERE operation_time BETWEEN ? AND ?
    ");
    $stmt->execute([$start_date, $end_date]);
    $result = $stmt->fetch();

    echo json_encode($result);
} catch (Exception $e) {
    http_response_code(500);
    error_log('资金查询失败: ' . $e->getMessage());
    echo json_encode(['error' => 'server_error']);
}
?>
