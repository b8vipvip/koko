<?php
// 引入 PHPMailer
require_once __DIR__ . '/db.php';
use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception;




$servername = "localhost"; // 替换为你的数据库服务器地址
$username = "kugo"; // 替换为你的数据库用户名
$password = "HP77C"; // 替换为你的数据库密码
$dbname = "kugo"; // 替换为你的数据库名
// 创建数据库连接
$conn = new mysqli($servername, $username, $password, $dbname);

// 检查连接
if ($conn->connect_error) {
    die("数据库连接失败: " . $conn->connect_error);
}

// 获取当前时间
$current_time = date('Y-m-d H:i:s');

// 计算1分钟前的时间
$five_minutes_ago = date('Y-m-d H:i:s', strtotime('-1 minutes'));

/// 查询条件：1分钟内创建、状态为“卡了”或“超时”、未发送过邮件 AND (r_status = '卡了' OR r_status = '超时')
$sql = "SELECT * FROM tel_data 
        WHERE create_date BETWEEN '$five_minutes_ago' AND '$current_time' 
        AND (r_status = '超时')
        
        AND email_sent = 0";
$result = $conn->query($sql);

if ($result->num_rows > 0) {
    // 遍历查询结果
    while ($row = $result->fetch_assoc()) {
        $id = $row['id'];
        $details = $row['details'];
        $r_status = $row['r_status'];

        // 创建 PHPMailer 实例
        $mail = new PHPMailer(true);

        try {
            // 配置 SMTP
            $mail->isSMTP();
            $mail->Host = 'smtp.qq.com'; // QQ邮箱SMTP服务器
            $mail->SMTPAuth = true;
            $mail->Username = '3891327165@qq.com'; // 发件人QQ邮箱
            $mail->Password = 'orrr'; // QQ邮箱授权码
            $mail->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS; // 启用SSL加密
            $mail->Port = 465; // QQ邮箱SMTP端口

            // 配置发件人和收件人
            $mail->setFrom('3891327165@qq.com', '555'); // 发件人邮箱和名称
            $mail->addAddress('3944268109@qq.com', '888'); // 收件人邮箱和名称


            // 邮件内容
            $mail->isHTML(true);
            $mail->Subject = '充值异常';
            $mail->Body = "异常状态: $r_status<br>异常详情: $details";

            // 发送邮件
            if ($mail->send()) {
                echo "邮件发送成功: ID $id, 状态: $r_status, 详情: $details<br>";
            
                // 标记为已发送
                $update_sql = "UPDATE tel_data SET email_sent = 1 WHERE id = $id";
                if ($conn->query($update_sql)) {
                    echo "记录 ID $id 已标记为已发送。<br>";
                } else {
                    echo "标记记录 ID $id 失败: " . $conn->error . "<br>";
                }
            } else {
                echo "邮件发送失败: ID $id, 状态: $r_status, 详情: $details<br>";
            }
        } catch (Exception $e) {
            echo "邮件发送失败: ID $id, 状态: $r_status, 详情: $details<br>错误信息: " . $mail->ErrorInfo . "<br>";
        }
    }
} else {
    echo "没有符合条件的记录。";
}

// 关闭数据库连接
$conn->close();
?>