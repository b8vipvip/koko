<?php
header('Content-Type: application/json');
require_once '../db.php';
koko_require_admin_token(false);

$data = json_decode(file_get_contents('php://input'), true);
$device_id = (int)$data['device_id'];
$amount = (float)$data['amount'];

if (!in_array($device_id, [157, 178,188,198,208,308]) || $amount <= 0) {
    http_response_code(400);
    echo json_encode(['error' => '参数错误']);
    exit;
}

try {
    $pdo->beginTransaction();

    // 获取最新余额
    $stmt = $pdo->prepare("SELECT balance FROM device_fund_details WHERE device_id = ? ORDER BY operation_time DESC, id DESC LIMIT 1");
    $stmt->execute([$device_id]);
    $last_balance = $stmt->fetchColumn() ?? 0;

    // 新余额
    $new_balance = $last_balance + $amount;

    // 插入记录
    $stmt = $pdo->prepare("INSERT INTO device_fund_details (device_id, fund_in, manual_fund_out, auto_fund_out, balance, operation_time) VALUES (?, ?, 0, 0, ?, NOW())");
    $stmt->execute([$device_id, $amount, $new_balance]);

    $pdo->commit();

    echo json_encode(['message' => '转入成功', 'balance' => $new_balance]);
} catch (Exception $e) {
    $pdo->rollBack();
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage()]);
}
?>
