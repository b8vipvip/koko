<?php
header('Content-Type: application/json');
require_once '../db.php';

try {
    $device_ids = [157, 178,188,198,208,308];
    $balances = [];

    foreach ($device_ids as $device_id) {
        $stmt = $pdo->prepare("SELECT balance FROM device_fund_details WHERE device_id = ? ORDER BY operation_time DESC, id DESC LIMIT 1");
        $stmt->execute([$device_id]);
        $balance = $stmt->fetchColumn() ?? 0;
        $balances["balance_$device_id"] = (float)$balance;
    }

    echo json_encode($balances);
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage()]);
}
?>
