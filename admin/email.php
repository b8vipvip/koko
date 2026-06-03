<?php
require_once __DIR__ . '/lib/config.php';
require_once __DIR__ . '/lib/mailer.php';
if (php_sapi_name() !== 'cli') {
    koko_require_admin();
}

try {
    $conn = koko_mysqli();
} catch (Throwable $e) {
    error_log('email.php 数据库连接失败: ' . $e->getMessage());
    http_response_code(500);
    echo '数据库连接失败';
    exit;
}

$current_time = date('Y-m-d H:i:s');
$five_minutes_ago = date('Y-m-d H:i:s', strtotime('-1 minutes'));

$stmt = $conn->prepare("SELECT id, details, r_status FROM tel_data WHERE create_date BETWEEN ? AND ? AND (r_status = '超时') AND email_sent = 0");
$stmt->bind_param('ss', $five_minutes_ago, $current_time);
$stmt->execute();
$result = $stmt->get_result();

if ($result && $result->num_rows > 0) {
    while ($row = $result->fetch_assoc()) {
        $id = (int)$row['id'];
        $details = $row['details'];
        $r_status = $row['r_status'];

        try {
            $mail = koko_create_mailer();
            $mail->isHTML(true);
            $mail->Subject = '充值异常';
            $mail->Body = "异常状态: $r_status<br>异常详情: $details";

            if ($mail->send()) {
                echo "邮件发送成功: ID $id, 状态: $r_status, 详情: $details<br>";
                $update_stmt = $conn->prepare('UPDATE tel_data SET email_sent = 1 WHERE id = ?');
                $update_stmt->bind_param('i', $id);
                if ($update_stmt->execute()) {
                    echo "记录 ID $id 已标记为已发送。<br>";
                } else {
                    echo "标记记录 ID $id 失败。<br>";
                }
                $update_stmt->close();
            }
        } catch (Throwable $e) {
            error_log('邮件发送失败: ' . $e->getMessage());
            echo "邮件发送失败: ID $id, 状态: $r_status, 详情: $details<br>";
        }
    }
} else {
    echo '没有符合条件的记录。';
}

$stmt->close();
$conn->close();
?>
