<?php

require_once __DIR__ . '/db.php';
use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception;
use PHPMailer\PHPMailer\SMTP;

require __DIR__ . '/vendor/autoload.php';

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

    // 检查设备 157 和 178 的余额
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
        $mail = new PHPMailer(true);
        $mail->isSMTP();
        $mail->Host = 'smtp.qq.com';
        $mail->SMTPAuth = true;
        $mail->Username = '3891327165@qq.com';
        $mail->Password = 'orrr'; // 请确认这个是 QQ 邮箱授权码
        $mail->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS;
        $mail->Port = 465;

        $mail->setFrom('3891327165@qq.com', '555');
        $mail->addAddress('3959418301@qq.com', '888');

        $mail->Subject = '设备余额不足';
        $mail->Body = "设备157余额：$balance_157 \n设备178余额：$balance_178";

        $mail->send();
        echo "告警邮件已发送\n";
    } else {
        echo "余额正常\n";
    }
} catch (Exception $e) {
    echo "发送失败: {$e->getMessage()}\n";
}
?>
