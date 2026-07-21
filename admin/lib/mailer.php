<?php
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
