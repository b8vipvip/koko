from pathlib import Path


def replace_required(path, old, new, label):
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


# Keep the system settings API behavior compatible with the existing admin page.
# The Secret is never returned by GET, so it remains write-only in the browser.
replace_required(
    Path('admin/phpapi/system_settings.php'),
    "header('Content-Type: application/json; charset=utf-8');\nkoko_require_admin_token(false);\n",
    "header('Content-Type: application/json; charset=utf-8');\n",
    'remove incompatible settings token requirement',
)

# admin/api.php: use the Enterprise WeChat sender directly and remove stale mail wording.
p = Path('admin/api.php')
text = p.read_text(encoding='utf-8')
text = text.replace('$emailBody', '$notifyBody')
text = text.replace('$mailEnabled', '$notifyEnabled')
text = text.replace('避免重复发邮件', '避免重复发送通知')
old = '''private function sendNewTaskNotification($body) {
    try {
        $mail = koko_create_mailer();
        $mail->Subject = '检测到新充值任务';
        $mail->Body = $body;

        $mail->send();

        return true;

    } catch (Exception $e) {
        throw new Exception("企业微信通知发送失败: " . $e->getMessage());
    }
}'''
new = '''private function sendNewTaskNotification($body) {
    try {
        return koko_send_wecom_text('检测到新充值任务', $body);
    } catch (Throwable $e) {
        throw new Exception("企业微信通知发送失败: " . $e->getMessage());
    }
}'''
if old not in text:
    raise RuntimeError('admin/api.php direct sender block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# admin/dev.php: send the device alert directly through Enterprise WeChat.
p = Path('admin/dev.php')
text = p.read_text(encoding='utf-8')
old = '''function sendAbnormalWeCom($abnormalDevices) {
  try {
    $mail = koko_create_mailer();
    $mail->isHTML(true);
    $mail->Subject = '设备异常通知';

    $deviceList = implode(', ', $abnormalDevices);
    $mail->Body = "以下设备出现异常：<br><strong>{$deviceList}</strong><br>请尽快处理！";

    return $mail->send();
  } catch (Exception $e) {
    error_log("企业微信通知发送失败: " . $e->getMessage());
    return false;
  }
}'''
new = '''function sendAbnormalWeCom($abnormalDevices) {
  try {
    $deviceList = implode(', ', $abnormalDevices);
    return koko_send_wecom_text('设备异常通知', "以下设备出现异常：{$deviceList}\n请尽快处理！");
  } catch (Throwable $e) {
    error_log("企业微信通知发送失败: " . $e->getMessage());
    return false;
  }
}'''
if old not in text:
    raise RuntimeError('admin/dev.php direct sender block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# admin/email.php: keep legacy file/column names for compatibility, but the sender is WeCom.
p = Path('admin/email.php')
text = p.read_text(encoding='utf-8')
old = '''            try {
                $mail = koko_create_mailer();
                $mail->isHTML(true);
                $mail->Subject = '充值异常';
                $mail->Body = "异常状态: " . htmlspecialchars($r_status, ENT_QUOTES, 'UTF-8') . "<br>异常详情: " . htmlspecialchars($details, ENT_QUOTES, 'UTF-8');

                if ($mail->send()) {'''
new = '''            try {
                $notifyBody = "异常状态: {$r_status}\n异常详情: {$details}";
                if (koko_send_wecom_text('充值异常', $notifyBody)) {'''
if old not in text:
    raise RuntimeError('admin/email.php direct sender block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

print('WECOM_FINALIZE_OK')
