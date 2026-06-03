<?php
require_once __DIR__ . '/db.php';
if (php_sapi_name() !== 'cli') {
    koko_require_admin();
}

try {
    $stmt = $pdo->query("SELECT id, dev, czp FROM order_data WHERE processed = 1 AND dev IN ('157','178','188','198','208','308') LIMIT 10");
    $orders = $stmt->fetchAll();

    foreach ($orders as $order) {
        $device_id = (int)$order['dev'];
        $czp = (float)$order['czp'];
        $order_id = (int)$order['id'];

        $pdo->beginTransaction();

        $stmt = $pdo->prepare("SELECT balance FROM device_fund_details WHERE device_id = ? ORDER BY operation_time DESC, id DESC LIMIT 1");
        $stmt->execute([$device_id]);
        $last_balance = $stmt->fetchColumn() ?? 0;

        $new_balance = $last_balance - $czp;

        $stmt = $pdo->prepare("INSERT INTO device_fund_details (device_id, fund_in, manual_fund_out, auto_fund_out, balance, operation_time) VALUES (?, 0, 0, ?, ?, NOW())");
        $stmt->execute([$device_id, $czp, $new_balance]);

        $stmt = $pdo->prepare("UPDATE order_data SET processed = 2 WHERE id = ?");
        $stmt->execute([$order_id]);

        $pdo->commit();

        echo "同步订单 {$order_id} 完成\n";
    }
} catch (Exception $e) {
    $pdo->rollBack();
    error_log('自动同步失败: ' . $e->getMessage());
    echo '同步失败';
}
?>
