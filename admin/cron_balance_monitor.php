<?php
require_once __DIR__ . '/db.php';
koko_require_admin_token(true);
require_once __DIR__ . '/lib/mailer.php';

$threshold = 100;

try {
    // 获取每个 device_id 最新的一条记录
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

    $balance_157 = $balances[157] ?? 0;
    $balance_178 = $balances[178] ?? 0;
    $balance_188 = $balances[188] ?? 0;
    $balance_198 = $balances[198] ?? 0;
    $balance_208 = $balances[208] ?? 0;
    $balance_308 = $balances[308] ?? 0;
    echo "设备157当前余额：$balance_157\n";
    echo "设备178当前余额：$balance_178\n";
    echo "设备188当前余额：$balance_188\n";
    echo "设备198当前余额：$balance_198\n";
    echo "设备208当前余额：$balance_208\n";
    echo "设备308当前余额：$balance_308\n";

    if ($balance_157 < $threshold || $balance_178 < $threshold || $balance_188 < $threshold || $balance_198 < $threshold || $balance_208 < $threshold || $balance_308 < $threshold) {
        $mail = koko_create_mailer();
        $mail->Subject = '设备余额不足';
        $mail->Body = "设备157余额：$balance_157 \n设备178余额：$balance_178 \n设备188余额：$balance_188 \n设备198余额：$balance_198 \n设备208余额：$balance_208 \n设备308余额：$balance_308";

        $mail->send();
        echo "告警邮件已发送\n";
    } else {
        echo "余额正常\n";
    }
} catch (Exception $e) {
    echo "发送失败: {$e->getMessage()}\n";
}
?>
