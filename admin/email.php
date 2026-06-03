<?php
// 充值异常邮件提醒。数据库与 SMTP 配置统一来自 admin/lib/config.php / .env。
require_once __DIR__ . '/db.php';
koko_require_admin_token(true);
require_once __DIR__ . '/lib/mailer.php';

try {
    $conn = koko_mysqli();
    if ($conn->connect_error) {
        throw new RuntimeException('db_connect_error');
    }

    // 获取当前时间
    $current_time = date('Y-m-d H:i:s');

    // 计算1分钟前的时间
    $five_minutes_ago = date('Y-m-d H:i:s', strtotime('-1 minutes'));

    /// 查询条件：1分钟内创建、状态为“卡了”或“超时”、未发送过邮件 AND (r_status = '卡了' OR r_status = '超时')
    $stmt = $conn->prepare("SELECT id, details, r_status FROM tel_data WHERE create_date BETWEEN ? AND ? AND (r_status = '超时') AND email_sent = 0");
    $stmt->bind_param('ss', $five_minutes_ago, $current_time);
    $stmt->execute();
    $result = $stmt->get_result();

    if ($result->num_rows > 0) {
        // 遍历查询结果
        while ($row = $result->fetch_assoc()) {
            $id = (int)$row['id'];
            $details = $row['details'];
            $r_status = $row['r_status'];

            try {
                $mail = koko_create_mailer();
                $mail->isHTML(true);
                $mail->Subject = '充值异常';
                $mail->Body = "异常状态: " . htmlspecialchars($r_status, ENT_QUOTES, 'UTF-8') . "<br>异常详情: " . htmlspecialchars($details, ENT_QUOTES, 'UTF-8');

                if ($mail->send()) {
                    echo "邮件发送成功: ID $id, 状态: $r_status, 详情: $details<br>";

                    // 标记为已发送
                    $update_stmt = $conn->prepare("UPDATE tel_data SET email_sent = 1 WHERE id = ?");
                    $update_stmt->bind_param('i', $id);
                    if ($update_stmt->execute()) {
                        echo "记录 ID $id 已标记为已发送。<br>";
                    } else {
                        echo "标记记录 ID $id 失败: " . $conn->error . "<br>";
                    }
                    $update_stmt->close();
                } else {
                    echo "邮件发送失败: ID $id, 状态: $r_status, 详情: $details<br>";
                }
            } catch (Exception $e) {
                echo "邮件发送失败: ID $id, 状态: $r_status, 详情: $details<br>错误信息: " . $e->getMessage() . "<br>";
            }
        }
    } else {
        echo "没有符合条件的记录。";
    }

    $stmt->close();
    $conn->close();
} catch (Exception $e) {
    http_response_code(500);
    error_log('email.php failed: ' . $e->getMessage());
    echo "系统异常";
}
?>
