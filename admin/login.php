<?php
require_once __DIR__ . '/auth_lib.php';

$cfg = koko_auth_config();
if (!$cfg) {
    http_response_code(500);
    echo '登录配置不存在';
    exit;
}

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';

    $okUser = hash_equals((string)($cfg['username'] ?? 'admin'), (string)$username);
    $okPass = password_verify((string)$password, (string)($cfg['password_hash'] ?? ''));

    if ($okUser && $okPass) {
        $cookieName = $cfg['cookie_name'] ?? 'koko_admin_auth';
        $cookieValue = $cfg['cookie_value'] ?? '';
        $days = (int)($cfg['expire_days'] ?? 15);
        if ($days <= 0) $days = 15;

        setcookie($cookieName, $cookieValue, [
            'expires' => time() + $days * 86400,
            'path' => '/',
            'secure' => (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off'),
            'httponly' => true,
            'samesite' => 'Lax',
        ]);

        header('Location: /');
        exit;
    }

    $error = '用户名或密码错误';
}
?>
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>后台登录</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body{font-family:Arial,"Microsoft YaHei",sans-serif;background:#f5f7fb;margin:0}
    .box{width:360px;max-width:90%;margin:12vh auto;background:#fff;padding:28px;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.08)}
    h2{text-align:center;margin:0 0 22px}
    input{width:100%;height:42px;margin:8px 0;padding:0 12px;box-sizing:border-box;border:1px solid #ddd;border-radius:6px}
    button{width:100%;height:42px;margin-top:12px;background:#1677ff;color:#fff;border:0;border-radius:6px;font-size:16px}
    .err{color:#d93026;text-align:center;margin-bottom:10px}
  </style>
</head>
<body>
  <div class="box">
    <h2>后台登录</h2>
    <?php if ($error): ?><div class="err"><?=htmlspecialchars($error, ENT_QUOTES, 'UTF-8')?></div><?php endif; ?>
    <form method="post">
      <input name="username" placeholder="用户名" autocomplete="username" required>
      <input name="password" type="password" placeholder="密码" autocomplete="current-password" required>
      <button type="submit">登录</button>
    </form>
  </div>
</body>
</html>
