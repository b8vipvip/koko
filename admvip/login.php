<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>后台 Key 登录</title>
  <style>
    body{margin:0;background:#f5f6f8;font-family:Arial,"Microsoft YaHei",sans-serif;}
    .box{width:min(92vw,420px);margin:15vh auto;background:#fff;border-radius:12px;padding:24px;box-shadow:0 8px 28px rgba(0,0,0,.08);}
    h2{margin:0 0 18px;font-size:22px;}
    input{width:100%;box-sizing:border-box;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:16px;}
    button{width:100%;margin-top:14px;padding:12px;border:0;border-radius:8px;background:#1677ff;color:#fff;font-size:16px;cursor:pointer;}
    .tip{margin-top:12px;color:#777;font-size:13px;line-height:1.6;}
  </style>
</head>
<body>
  <div class="box">
    <h2>后台 Key 登录</h2>
    <input id="key" type="password" placeholder="请输入后台访问 Key" autofocus>
    <button onclick="login()">登录</button>
    <div class="tip">验证成功后由 Nginx 写入 Cookie。PHP 登录验证已停用。</div>
  </div>

  <script>
    function login(){
      var key = document.getElementById('key').value.trim();
      if(!key){
        alert('请输入 Key');
        return;
      }
      location.href = '/auth_key?key=' + encodeURIComponent(key);
    }

    document.getElementById('key').addEventListener('keydown', function(e){
      if(e.key === 'Enter') login();
    });
  </script>
</body>
</html>
