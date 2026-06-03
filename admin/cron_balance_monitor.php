<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/lib/mailer.php';
if (php_sapi_name() !== 'cli') {
    koko_require_admin();
}

$threshold = 100;

try {
    $sql = "
        SELECT d.device_id, d.balance
        FROM device_fund_details d
        INNER JOIN (
            SELECT device_id, MAX(id) AS latest_id
            FROM device_fund_details
            GROUP BY device_id
        ) AS latest
        ON d.device_id = latest.device_id AND d.id = latest.latest_id
    ";

    $stmt = $pdo->query($sql);
    $balances = [];
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        $balances[$row['device_id']] = $row['balance'];
    }

    $deviceIds = [157, 178, 188, 198, 208, 308];
    foreach ($deviceIds as $deviceId) {
        $balance = $balances[$deviceId] ?? 0;
        echo "设备{$deviceId}当前余额：{$balance}\n";
    }

    $hasLowBalance = false;
    foreach ($deviceIds as $deviceId) {
        if (($balances[$deviceId] ?? 0) < $threshold) {
            $hasLowBalance = true;
            break;
        }
    }

    if ($hasLowBalance) {
        $mail = koko_create_mailer();
        $mail->Subject = '设备余额不足';
        $bodyLines = [];
        foreach ($deviceIds as $deviceId) {
            $bodyLines[] = "设备{$deviceId}余额：" . ($balances[$deviceId] ?? 0);
        }
        $mail->Body = implode("\n", $bodyLines);
        $mail->send();
        echo "告警邮件已发送\n";
    } else {
        echo "余额正常\n";
    }
} catch (Throwable $e) {
    error_log('余额监控失败: ' . $e->getMessage());
    echo "发送失败\n";
}
?>
