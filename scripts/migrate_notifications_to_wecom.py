from pathlib import Path
import re


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text, pattern, replacement, label, flags=0):
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return new_text


# -----------------------------------------------------------------------------
# admin/lib/config.php
# -----------------------------------------------------------------------------
p = Path("admin/lib/config.php")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    "            'mail_last_sent_new_task_at' => '',\n",
    "            'mail_last_sent_new_task_at' => '',\n"
    "            'wecom_corp_id' => '',\n"
    "            'wecom_agent_secret' => '',\n"
    "            'wecom_agent_id' => '',\n"
    "            'wecom_to_user' => '@all',\n"
    "            'wecom_to_party' => '',\n"
    "            'wecom_to_tag' => '',\n",
    "config defaults",
)
text = sub_once(
    text,
    r"\nif \(!function_exists\('koko_mail_config'\)\) \{.*?\n\}\n(?=\nif \(!function_exists\('koko_admin_token'\)\))",
    "\n",
    "remove SMTP config helper",
    flags=re.S,
)
p.write_text(text, encoding="utf-8")


# -----------------------------------------------------------------------------
# admin/lib/mailer.php -- keep koko_create_mailer() as a compatibility adapter,
# but every send now goes through Enterprise WeChat.
# -----------------------------------------------------------------------------
Path("admin/lib/mailer.php").write_text(r'''<?php
require_once __DIR__ . '/config.php';

if (!function_exists('koko_wecom_config')) {
    function koko_wecom_config() {
        return [
            'corp_id' => trim((string)koko_get_setting('wecom_corp_id', '')),
            'agent_secret' => trim((string)koko_get_setting('wecom_agent_secret', '')),
            'agent_id' => (int)koko_get_setting('wecom_agent_id', '0'),
            'to_user' => trim((string)koko_get_setting('wecom_to_user', '@all')),
            'to_party' => trim((string)koko_get_setting('wecom_to_party', '')),
            'to_tag' => trim((string)koko_get_setting('wecom_to_tag', '')),
        ];
    }
}

if (!function_exists('koko_wecom_http_json')) {
    function koko_wecom_http_json($method, $url, $payload = null) {
        if (!function_exists('curl_init')) {
            throw new RuntimeException('PHP cURL 扩展未安装，无法发送企业微信通知');
        }

        $ch = curl_init($url);
        $options = [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_TIMEOUT => 12,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_CUSTOMREQUEST => strtoupper($method),
        ];

        if ($payload !== null) {
            $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
            if ($json === false) {
                throw new RuntimeException('企业微信通知 JSON 编码失败');
            }
            $options[CURLOPT_HTTPHEADER] = ['Content-Type: application/json; charset=utf-8'];
            $options[CURLOPT_POSTFIELDS] = $json;
        }

        curl_setopt_array($ch, $options);
        $body = curl_exec($ch);
        $error = curl_error($ch);
        $status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($body === false || $error !== '') {
            throw new RuntimeException('企业微信接口请求失败: ' . $error);
        }
        if ($status < 200 || $status >= 300) {
            throw new RuntimeException('企业微信接口 HTTP 状态异常: ' . $status);
        }

        $data = json_decode($body, true);
        if (!is_array($data)) {
            throw new RuntimeException('企业微信接口返回非 JSON 数据');
        }
        return $data;
    }
}

if (!function_exists('koko_wecom_get_access_token')) {
    function koko_wecom_get_access_token() {
        static $cachedToken = '';
        static $cachedUntil = 0;

        if ($cachedToken !== '' && $cachedUntil > time() + 60) {
            return $cachedToken;
        }

        $cfg = koko_wecom_config();
        if ($cfg['corp_id'] === '' || $cfg['agent_secret'] === '') {
            throw new RuntimeException('企业微信 CorpID 或应用 Secret 未配置');
        }

        $url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken?' . http_build_query([
            'corpid' => $cfg['corp_id'],
            'corpsecret' => $cfg['agent_secret'],
        ]);
        $result = koko_wecom_http_json('GET', $url);
        if ((int)($result['errcode'] ?? -1) !== 0 || empty($result['access_token'])) {
            throw new RuntimeException('获取企业微信 access_token 失败: ' . ($result['errmsg'] ?? 'unknown'));
        }

        $cachedToken = (string)$result['access_token'];
        $expiresIn = max(120, (int)($result['expires_in'] ?? 7200));
        $cachedUntil = time() + $expiresIn - 120;
        return $cachedToken;
    }
}

if (!function_exists('koko_wecom_normalize_text')) {
    function koko_wecom_normalize_text($text) {
        $text = preg_replace('/<br\s*\/?>/i', "\n", (string)$text);
        $text = html_entity_decode(strip_tags($text), ENT_QUOTES | ENT_HTML5, 'UTF-8');
        return trim($text);
    }
}

if (!function_exists('koko_wecom_split_text')) {
    function koko_wecom_split_text($text, $maxBytes = 1800) {
        $text = (string)$text;
        if (strlen($text) <= $maxBytes) {
            return [$text];
        }

        $chunks = [];
        while ($text !== '') {
            if (function_exists('mb_strcut')) {
                $chunk = mb_strcut($text, 0, $maxBytes, 'UTF-8');
                $text = (string)mb_strcut($text, strlen($chunk), null, 'UTF-8');
            } else {
                $chunk = substr($text, 0, $maxBytes);
                $text = substr($text, $maxBytes);
            }
            if ($chunk === '') {
                break;
            }
            $chunks[] = $chunk;
        }
        return $chunks ?: [''];
    }
}

if (!function_exists('koko_send_wecom_text')) {
    function koko_send_wecom_text($subject, $body) {
        $cfg = koko_wecom_config();
        if ($cfg['corp_id'] === '' || $cfg['agent_secret'] === '' || $cfg['agent_id'] <= 0) {
            throw new RuntimeException('企业微信 CorpID、应用 Secret 或 AgentId 未完整配置');
        }
        if ($cfg['to_user'] === '' && $cfg['to_party'] === '' && $cfg['to_tag'] === '') {
            throw new RuntimeException('企业微信接收成员、部门、标签至少配置一项');
        }

        $content = trim('【' . trim((string)$subject) . '】' . "\n" . koko_wecom_normalize_text($body));
        $token = koko_wecom_get_access_token();

        foreach (koko_wecom_split_text($content) as $chunk) {
            $payload = [
                'msgtype' => 'text',
                'agentid' => $cfg['agent_id'],
                'text' => ['content' => $chunk],
                'safe' => 0,
            ];
            if ($cfg['to_user'] !== '') $payload['touser'] = $cfg['to_user'];
            if ($cfg['to_party'] !== '') $payload['toparty'] = $cfg['to_party'];
            if ($cfg['to_tag'] !== '') $payload['totag'] = $cfg['to_tag'];

            $url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=' . rawurlencode($token);
            $result = koko_wecom_http_json('POST', $url, $payload);
            $errcode = (int)($result['errcode'] ?? -1);

            if (in_array($errcode, [40014, 42001], true)) {
                // PHP 请求内的静态缓存无法手工清空，重新直接取一次新 token 后重试。
                $tokenResult = koko_wecom_http_json('GET', 'https://qyapi.weixin.qq.com/cgi-bin/gettoken?' . http_build_query([
                    'corpid' => $cfg['corp_id'],
                    'corpsecret' => $cfg['agent_secret'],
                ]));
                if ((int)($tokenResult['errcode'] ?? -1) !== 0 || empty($tokenResult['access_token'])) {
                    throw new RuntimeException('刷新企业微信 access_token 失败: ' . ($tokenResult['errmsg'] ?? 'unknown'));
                }
                $token = (string)$tokenResult['access_token'];
                $url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=' . rawurlencode($token);
                $result = koko_wecom_http_json('POST', $url, $payload);
                $errcode = (int)($result['errcode'] ?? -1);
            }

            if ($errcode !== 0) {
                throw new RuntimeException('企业微信通知发送失败: ' . ($result['errmsg'] ?? ('errcode=' . $errcode)));
            }
        }
        return true;
    }
}

if (!class_exists('KokoWeComNotifier')) {
    class KokoWeComNotifier {
        public $Subject = '';
        public $Body = '';
        private $html = false;

        public function isHTML($enabled = true) {
            $this->html = (bool)$enabled;
            return $this;
        }

        public function send() {
            $body = $this->html ? koko_wecom_normalize_text($this->Body) : (string)$this->Body;
            return koko_send_wecom_text((string)$this->Subject, $body);
        }
    }
}

// 兼容旧代码：所有历史 koko_create_mailer()->send() 调用现在实际发送企业微信通知。
if (!function_exists('koko_create_mailer')) {
    function koko_create_mailer() {
        return new KokoWeComNotifier();
    }
}

if (!function_exists('koko_send_backend_error_notification')) {
    function koko_send_backend_error_notification($context, $message) {
        if (koko_get_setting('notify_backend_error', '1') !== '1') {
            return false;
        }
        if (!koko_mail_cooldown_ready('mail_last_sent_backend_error_at')) {
            return false;
        }

        try {
            $sent = koko_send_wecom_text('Koko 后端运行报错', "运行位置：{$context}\n错误信息：{$message}");
            if ($sent) {
                koko_mark_mail_sent('mail_last_sent_backend_error_at');
            }
            return $sent;
        } catch (Throwable $notifyError) {
            error_log('Enterprise WeChat backend error notification failed: ' . $notifyError->getMessage());
            return false;
        }
    }
}

// 旧函数名保留作兼容层，但不再发送邮件。
if (!function_exists('koko_send_backend_error_mail')) {
    function koko_send_backend_error_mail($context, $message) {
        return koko_send_backend_error_notification($context, $message);
    }
}
''', encoding="utf-8")


# -----------------------------------------------------------------------------
# admin/phpapi/system_settings.php
# -----------------------------------------------------------------------------
Path("admin/phpapi/system_settings.php").write_text(r'''<?php
require_once __DIR__ . '/../lib/config.php';

header('Content-Type: application/json; charset=utf-8');
koko_require_admin_token(false);

function koko_system_setting_keys() {
    return [
        'redeem_url',
        'notify_device_offline',
        'notify_new_recharge_task',
        'notify_backend_error',
        'usrvip_site_schedule_enabled',
        'usrvip_site_close_time',
        'usrvip_site_open_time',
        'usrvip_site_closed_message',
        'wecom_corp_id',
        'wecom_agent_secret',
        'wecom_agent_id',
        'wecom_to_user',
        'wecom_to_party',
        'wecom_to_tag',
    ];
}

function koko_validate_hhmm($value, $field) {
    $value = trim((string)$value);
    if (!preg_match('/^\d{2}:\d{2}$/', $value)) {
        throw new InvalidArgumentException($field . ' 必须为 HH:MM');
    }
    [$hh, $mm] = array_map('intval', explode(':', $value));
    if ($hh > 23 || $mm > 59) {
        throw new InvalidArgumentException($field . ' 必须为 HH:MM');
    }
    return $value;
}

try {
    $pdo = koko_pdo();
    koko_ensure_system_settings($pdo);

    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $stmt = $pdo->prepare('SELECT setting_key, setting_value FROM system_settings WHERE setting_key = ? LIMIT 1');
        $settings = [];
        foreach (koko_system_setting_keys() as $key) {
            $stmt->execute([$key]);
            $value = $stmt->fetchColumn();
            $settings[$key] = $value === false || $value === null ? (koko_default_settings()[$key] ?? '') : (string)$value;
        }

        // Secret 只允许写入，不回传到浏览器，避免后台页面或网络响应泄露。
        $settings['wecom_agent_secret_configured'] = trim((string)$settings['wecom_agent_secret']) !== '';
        $settings['wecom_agent_secret'] = '';
        $settings['wecom_configured'] = (
            trim((string)$settings['wecom_corp_id']) !== ''
            && $settings['wecom_agent_secret_configured']
            && (int)$settings['wecom_agent_id'] > 0
            && (
                trim((string)$settings['wecom_to_user']) !== ''
                || trim((string)$settings['wecom_to_party']) !== ''
                || trim((string)$settings['wecom_to_tag']) !== ''
            )
        );

        echo json_encode(['success' => true, 'settings' => $settings], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }

    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        http_response_code(405);
        echo json_encode(['success' => false, 'message' => 'Method not allowed'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $payload = json_decode(file_get_contents('php://input'), true);
    if (!is_array($payload) && !empty($_POST)) {
        $payload = $_POST;
    }
    if (!is_array($payload)) {
        throw new InvalidArgumentException('请求 JSON 无效');
    }

    $values = [];
    foreach (koko_system_setting_keys() as $key) {
        if (!array_key_exists($key, $payload)) {
            continue;
        }
        $value = $payload[$key];
        if (in_array($key, ['notify_device_offline', 'notify_new_recharge_task', 'notify_backend_error', 'usrvip_site_schedule_enabled'], true)) {
            $value = ((string)$value === '1' || $value === 1 || $value === true) ? '1' : '0';
        } elseif (in_array($key, ['usrvip_site_close_time', 'usrvip_site_open_time'], true)) {
            $value = koko_validate_hhmm($value, $key);
        } elseif ($key === 'wecom_agent_id') {
            $value = trim((string)$value);
            if ($value !== '' && (!ctype_digit($value) || (int)$value <= 0)) {
                throw new InvalidArgumentException('企业微信 AgentId 必须为正整数');
            }
        } else {
            $value = trim((string)$value);
        }

        // Secret 留空代表保持原值，避免编辑其它配置时清空密钥。
        if ($key === 'wecom_agent_secret' && $value === '') {
            continue;
        }
        $values[$key] = $value;
    }

    $stmt = $pdo->prepare(
        'INSERT INTO system_settings (setting_key, setting_value, updated_at) VALUES (?, ?, NOW())
         ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), updated_at = NOW()'
    );
    foreach ($values as $key => $value) {
        $stmt->execute([$key, $value]);
    }

    echo json_encode(['success' => true, 'message' => '保存成功'], JSON_UNESCAPED_UNICODE);
} catch (Throwable $e) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => $e->getMessage()], JSON_UNESCAPED_UNICODE);
}
''', encoding="utf-8")


# -----------------------------------------------------------------------------
# admin/index.html active system-settings override
# -----------------------------------------------------------------------------
p = Path("admin/index.html")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    "        notify_new_recharge_task: 1\n",
    "        notify_new_recharge_task: 1,\n"
    "        wecom_corp_id: '',\n"
    "        wecom_agent_secret: '',\n"
    "        wecom_agent_secret_configured: false,\n"
    "        wecom_agent_id: '',\n"
    "        wecom_to_user: '@all',\n"
    "        wecom_to_party: '',\n"
    "        wecom_to_tag: ''\n",
    "admin settings fallback",
)

insert_after = '''  function rowHtml(id, title, desc, checked) {
    return ''
      + '<div class="koko-setting-row" style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid #f0f0f0;">'
      + '  <div style="flex:1;min-width:0;">'
      + '    <div style="font-weight:600;color:#222;font-size:14px;">' + title + '</div>'
      + '    <div style="font-size:12px;color:#888;line-height:1.5;margin-top:4px;">' + desc + '</div>'
      + '  </div>'
      + '  <label style="display:flex;align-items:center;gap:6px;white-space:nowrap;font-size:13px;color:#333;">'
      + '    <input id="' + id + '" type="checkbox" ' + (checked ? 'checked' : '') + '>'
      + '    开启'
      + '  </label>'
      + '</div>';
  }
'''
input_helpers = insert_after + '''
  function escapeAttr(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function inputHtml(id, title, desc, value, placeholder, type) {
    return ''
      + '<div class="koko-setting-row" style="padding:12px 0;border-bottom:1px solid #f0f0f0;">'
      + '  <div style="font-weight:600;color:#222;font-size:14px;margin-bottom:4px;">' + title + '</div>'
      + '  <div style="font-size:12px;color:#888;line-height:1.5;margin-bottom:7px;">' + desc + '</div>'
      + '  <input id="' + id + '" type="' + (type || 'text') + '" value="' + escapeAttr(value || '') + '" placeholder="' + escapeAttr(placeholder || '') + '" style="width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid #ddd;border-radius:5px;">'
      + '</div>';
  }
'''
text = replace_once(text, insert_after, input_helpers, "admin input helpers")

text = sub_once(
    text,
    r"  function openSettingsModal\(settings\) \{.*?\n  \}\n\n  async function handleSystemConfigClick",
    r'''  function openSettingsModal(settings) {
    var backendError = toBool(getSetting(settings, 'notify_backend_error', 1));
    var deviceOffline = toBool(getSetting(settings, 'notify_device_offline', 1));
    var newRecharge = toBool(getSetting(settings, 'notify_new_recharge_task', 1));
    var secretConfigured = toBool(getSetting(settings, 'wecom_agent_secret_configured', false));

    var html = ''
      + '<div id="koko-system-settings-v8" style="padding:14px 18px 4px;background:#fff;box-sizing:border-box;max-height:72vh;overflow-y:auto;">'
      + '<div style="font-size:15px;font-weight:700;color:#111;padding:4px 0 8px;">企业微信自建应用</div>'
      + inputHtml('kokoWecomCorpId', '企业 ID（CorpID）', '企业微信管理后台「我的企业」中的企业 ID。', getSetting(settings, 'wecom_corp_id', ''), 'wwxxxxxxxxxxxxxxxx', 'text')
      + inputHtml('kokoWecomAgentSecret', '应用 Secret', '自建应用的 Secret。为安全起见已配置的 Secret 不会从服务器回显，留空表示不修改。', '', secretConfigured ? '已配置，留空不修改' : '请输入应用 Secret', 'password')
      + inputHtml('kokoWecomAgentId', '应用 AgentId', '自建应用详情页中的 AgentId（正整数）。', getSetting(settings, 'wecom_agent_id', ''), '例如 1000002', 'number')
      + inputHtml('kokoWecomToUser', '接收成员', '支持 @all，或使用竖线分隔多个企业微信成员账号，例如 user1|user2。', getSetting(settings, 'wecom_to_user', '@all'), '@all', 'text')
      + inputHtml('kokoWecomToParty', '接收部门（可选）', '多个部门 ID 使用竖线分隔；未使用可留空。', getSetting(settings, 'wecom_to_party', ''), '例如 1|2', 'text')
      + inputHtml('kokoWecomToTag', '接收标签（可选）', '多个标签 ID 使用竖线分隔；未使用可留空。', getSetting(settings, 'wecom_to_tag', ''), '例如 1|3', 'text')
      + '<div style="font-size:15px;font-weight:700;color:#111;padding:16px 0 2px;">通知开关</div>'
      + rowHtml('kokoNotifyBackendError', '后端错误企业微信通知', '后端接口、任务或系统异常时发送企业微信提醒。', backendError)
      + rowHtml('kokoNotifyDeviceOffline', '设备离线企业微信通知', '检测到设备掉线、异常不可用时发送企业微信提醒。', deviceOffline)
      + rowHtml('kokoNotifyNewRechargeTask', '新充值任务企业微信通知', '收到新的正式充值任务或待处理任务时发送企业微信提醒。', newRecharge)
      + '<div style="font-size:12px;color:#999;line-height:1.6;margin-top:12px;">通知接口统一由后端调用企业微信自建应用发送；原 SMTP 邮箱通知逻辑已停用。</div>'
      + '</div>';

    if (!window.layer || !layer.open) {
      alert('系统配置弹窗组件未加载');
      return;
    }

    layer.open({
      type: 1,
      title: '系统配置',
      area: ['min(94vw, 680px)', 'auto'],
      content: html,
      btn: ['保存', '取消'],
      yes: async function (index) {
        var payload = {
          wecom_corp_id: document.getElementById('kokoWecomCorpId').value.trim(),
          wecom_agent_secret: document.getElementById('kokoWecomAgentSecret').value.trim(),
          wecom_agent_id: document.getElementById('kokoWecomAgentId').value.trim(),
          wecom_to_user: document.getElementById('kokoWecomToUser').value.trim(),
          wecom_to_party: document.getElementById('kokoWecomToParty').value.trim(),
          wecom_to_tag: document.getElementById('kokoWecomToTag').value.trim(),
          notify_backend_error: document.getElementById('kokoNotifyBackendError').checked ? 1 : 0,
          notify_device_offline: document.getElementById('kokoNotifyDeviceOffline').checked ? 1 : 0,
          notify_new_recharge_task: document.getElementById('kokoNotifyNewRechargeTask').checked ? 1 : 0
        };

        try {
          var json = await saveSettings(payload);
          if (json && json.success === false) {
            throw new Error(json.message || json.error || '保存失败');
          }
          layer.msg('企业微信配置保存成功');
          layer.close(index);
        } catch (e) {
          layer.alert('保存失败：' + e.message);
        }
      }
    });
  }

  async function handleSystemConfigClick''',
    "admin active settings modal",
    flags=re.S,
)
p.write_text(text, encoding="utf-8")


# -----------------------------------------------------------------------------
# server/koko_task_helpers.py
# -----------------------------------------------------------------------------
p = Path("server/koko_task_helpers.py")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    "import os\nimport re\nimport smtplib\nfrom datetime import datetime, time as dt_time\nfrom email.mime.text import MIMEText\n",
    "import json\nimport os\nimport re\nimport time\nimport urllib.parse\nimport urllib.request\nfrom datetime import datetime, time as dt_time\n",
    "python imports",
)
text = replace_once(
    text,
    '    "mail_last_sent_new_task_at": "",\n',
    '    "mail_last_sent_new_task_at": "",\n'
    '    "wecom_corp_id": "",\n'
    '    "wecom_agent_secret": "",\n'
    '    "wecom_agent_id": "",\n'
    '    "wecom_to_user": "@all",\n'
    '    "wecom_to_party": "",\n'
    '    "wecom_to_tag": "",\n',
    "python defaults",
)
text = sub_once(
    text,
    r"def send_new_task_mail\(rows\):.*?\n\n(?=def notify_new_tasks\(conn, limit=20\):)",
    r'''_WECOM_TOKEN_CACHE = {"access_token": "", "expires_at": 0.0}


def get_wecom_config(cursor):
    return {
        "corp_id": get_setting(cursor, "wecom_corp_id", "").strip(),
        "agent_secret": get_setting(cursor, "wecom_agent_secret", "").strip(),
        "agent_id": get_setting(cursor, "wecom_agent_id", "").strip(),
        "to_user": get_setting(cursor, "wecom_to_user", "@all").strip(),
        "to_party": get_setting(cursor, "wecom_to_party", "").strip(),
        "to_tag": get_setting(cursor, "wecom_to_tag", "").strip(),
    }


def _wecom_http_json(url, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(request, timeout=12) as response:
        body = response.read().decode("utf-8", errors="replace")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise RuntimeError("企业微信接口返回格式异常")
    return result


def get_wecom_access_token(cursor, force_refresh=False):
    now = time.time()
    if (
        not force_refresh
        and _WECOM_TOKEN_CACHE.get("access_token")
        and float(_WECOM_TOKEN_CACHE.get("expires_at") or 0) > now + 60
    ):
        return _WECOM_TOKEN_CACHE["access_token"]

    cfg = get_wecom_config(cursor)
    if not cfg["corp_id"] or not cfg["agent_secret"]:
        raise RuntimeError("企业微信 CorpID 或应用 Secret 未配置")

    url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken?" + urllib.parse.urlencode({
        "corpid": cfg["corp_id"],
        "corpsecret": cfg["agent_secret"],
    })
    result = _wecom_http_json(url)
    if int(result.get("errcode", -1)) != 0 or not result.get("access_token"):
        raise RuntimeError("获取企业微信 access_token 失败: {}".format(result.get("errmsg", "unknown")))

    token = str(result["access_token"])
    expires_in = max(120, int(result.get("expires_in") or 7200))
    _WECOM_TOKEN_CACHE["access_token"] = token
    _WECOM_TOKEN_CACHE["expires_at"] = now + expires_in - 120
    return token


def _split_wecom_text(text, max_bytes=1800):
    text = str(text or "")
    chunks = []
    current = []
    current_bytes = 0
    for char in text:
        char_bytes = len(char.encode("utf-8"))
        if current and current_bytes + char_bytes > max_bytes:
            chunks.append("".join(current))
            current = []
            current_bytes = 0
        current.append(char)
        current_bytes += char_bytes
    if current:
        chunks.append("".join(current))
    return chunks or [""]


def send_wecom_text(cursor, subject, body):
    cfg = get_wecom_config(cursor)
    try:
        agent_id = int(cfg["agent_id"])
    except (TypeError, ValueError):
        agent_id = 0
    if not cfg["corp_id"] or not cfg["agent_secret"] or agent_id <= 0:
        raise RuntimeError("企业微信 CorpID、应用 Secret 或 AgentId 未完整配置")
    if not (cfg["to_user"] or cfg["to_party"] or cfg["to_tag"]):
        raise RuntimeError("企业微信接收成员、部门、标签至少配置一项")

    content = "【{}】\n{}".format(str(subject or "").strip(), str(body or "").strip()).strip()
    token = get_wecom_access_token(cursor)

    for chunk in _split_wecom_text(content):
        payload = {
            "msgtype": "text",
            "agentid": agent_id,
            "text": {"content": chunk},
            "safe": 0,
        }
        if cfg["to_user"]:
            payload["touser"] = cfg["to_user"]
        if cfg["to_party"]:
            payload["toparty"] = cfg["to_party"]
        if cfg["to_tag"]:
            payload["totag"] = cfg["to_tag"]

        def do_send(access_token):
            url = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=" + urllib.parse.quote(access_token, safe="")
            return _wecom_http_json(url, payload)

        result = do_send(token)
        errcode = int(result.get("errcode", -1))
        if errcode in (40014, 42001):
            token = get_wecom_access_token(cursor, force_refresh=True)
            result = do_send(token)
            errcode = int(result.get("errcode", -1))
        if errcode != 0:
            raise RuntimeError("企业微信通知发送失败: {}".format(result.get("errmsg", "errcode={}".format(errcode))))
    return True


def send_new_task_wecom(cursor, rows):
    if isinstance(rows, dict):
        rows = [rows]
    body_keys = ["id", "tel", "yzm", "orderID", "zhanghu", "r_status", "create_date", "submit_portal", "submit_domain"]
    blocks = []
    for idx, row in enumerate(rows, 1):
        blocks.append("任务 #{}\n{}".format(
            idx,
            "\n".join("{}: {}".format(k, row.get(k, "")) for k in body_keys if k in row),
        ))
    body = "本次扫描到 {} 条新充值任务：\n\n{}".format(len(rows), "\n\n".join(blocks))
    return send_wecom_text(cursor, "新充值任务通知", body)


''',
    "python replace SMTP sender",
    flags=re.S,
)
text = replace_once(
    text,
    "        if send_new_task_mail(rows):\n",
    "        if send_new_task_wecom(cursor, rows):\n",
    "python notify call",
)
p.write_text(text, encoding="utf-8")


# -----------------------------------------------------------------------------
# Known admin notification call sites: functionality is already converted by
# the compatibility adapter; update direct paths and user-facing wording too.
# -----------------------------------------------------------------------------
p = Path("admin/api.php")
text = p.read_text(encoding="utf-8")
text = text.replace("3. 发送邮件", "3. 发送企业微信通知")
text = text.replace("$this->sendNewTaskEmail($emailBody);", "$this->sendNewTaskNotification($emailBody);")
text = text.replace("新任务已写入 details，并已发送邮件", "新任务已写入 details，并已发送企业微信通知")
text = text.replace("新任务已写入 details，邮件通知已关闭", "新任务已写入 details，企业微信通知已关闭")
text = text.replace("private function sendNewTaskEmail($body)", "private function sendNewTaskNotification($body)")
text = text.replace('throw new Exception("邮件发送失败: " . $e->getMessage());', 'throw new Exception("企业微信通知发送失败: " . $e->getMessage());')
p.write_text(text, encoding="utf-8")

p = Path("admin/dev.php")
text = p.read_text(encoding="utf-8")
text = text.replace("// ✅ 发邮件", "// ✅ 发企业微信通知")
text = text.replace("function sendAbnormalMail($abnormalDevices)", "function sendAbnormalWeCom($abnormalDevices)")
text = text.replace("邮件发送失败: ", "企业微信通知发送失败: ")
text = text.replace("// 邮件节流：", "// 通知节流：")
text = text.replace("$ok = sendAbnormalMail($abnormalDevices);", "$ok = sendAbnormalWeCom($abnormalDevices);")
text = text.replace("koko_send_backend_error_mail('admin/dev.php'", "koko_send_backend_error_notification('admin/dev.php'")
p.write_text(text, encoding="utf-8")

p = Path("admin/email.php")
text = p.read_text(encoding="utf-8")
text = text.replace("充值异常邮件提醒", "充值异常企业微信提醒")
text = text.replace("数据库与 SMTP 配置统一来自 admin/lib/config.php / .env。", "企业微信配置统一来自系统配置。")
text = text.replace("后端运行报错邮件通知已关闭。", "后端运行报错企业微信通知已关闭。")
text = text.replace("未发送过邮件", "未发送过通知")
text = text.replace("邮件发送成功", "企业微信通知发送成功")
text = text.replace("邮件发送失败", "企业微信通知发送失败")
text = text.replace("koko_send_backend_error_mail('admin/email.php'", "koko_send_backend_error_notification('admin/email.php'")
p.write_text(text, encoding="utf-8")

Path("admin/mail_test.php").write_text(r'''<?php
require_once __DIR__ . '/lib/mailer.php';

try {
    koko_require_admin_token(false);
    koko_send_wecom_text('企业微信测试通知', '这是一条来自 Koko 管理后台的企业微信测试通知。');
    echo "企业微信通知发送成功";
} catch (Throwable $e) {
    http_response_code(500);
    echo "企业微信通知发送失败：" . $e->getMessage();
}
''', encoding="utf-8")

p = Path("admin/cron_balance_monitor.php")
text = p.read_text(encoding="utf-8")
text = sub_once(
    text,
    r"\s*\$mail = koko_create_mailer\(\);\s*\n\s*\$mail->Subject = '设备余额不足';\s*\n\s*\$mail->Body = (?P<body>.*?);\s*\n\s*\$mail->send\(\);\s*\n\s*echo \"告警邮件已发送\\n\";",
    lambda m: "\n        $notifyBody = " + m.group("body") + ";\n        koko_send_wecom_text('设备余额不足', $notifyBody);\n        echo \"企业微信告警已发送\\n\";",
    "balance monitor sender",
    flags=re.S,
)
p.write_text(text, encoding="utf-8")

print("WECOM_MIGRATION_OK")
