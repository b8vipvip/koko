// KOKO_USRVIP_ACCESS_GUARD_V1
(function () {
  if (window.__KOKO_USRVIP_ACCESS_GUARD_V1__) return;
  window.__KOKO_USRVIP_ACCESS_GUARD_V1__ = true;

  function parseMinute(v) {
    v = String(v || '').trim();
    var m = v.match(/^(\d{1,2}):(\d{2})$/);
    if (!m) return null;
    var h = parseInt(m[1], 10);
    var mm = parseInt(m[2], 10);
    if (h < 0 || h > 23 || mm < 0 || mm > 59) return null;
    return h * 60 + mm;
  }

  function isAllowed(nowMin, startMin, endMin) {
    if (startMin === null || endMin === null) return true;

    if (startMin === endMin) {
      return true;
    }

    if (startMin < endMin) {
      return nowMin >= startMin && nowMin < endMin;
    }

    // 跨天，例如 22:00-06:00
    return nowMin >= startMin || nowMin < endMin;
  }

  function blockPage(message, openTime, closeTime) {
    var text = message || ('当前不在站点开放时间内，开放时间：' + openTime + '-' + closeTime);

    var css = [
      'html,body{margin:0!important;padding:0!important;width:100%!important;height:100%!important;background:#f5f7fb!important;}',
      '.koko-site-closed-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,"Microsoft YaHei",sans-serif;}',
      '.koko-site-closed-card{width:min(520px,92vw);background:#fff;border-radius:14px;box-shadow:0 10px 35px rgba(0,0,0,.08);padding:28px 22px;text-align:center;color:#222;}',
      '.koko-site-closed-title{font-size:20px;font-weight:700;margin-bottom:12px;}',
      '.koko-site-closed-msg{font-size:15px;line-height:1.8;white-space:pre-wrap;color:#555;}',
      '.koko-site-closed-time{margin-top:16px;font-size:13px;color:#999;}'
    ].join('');

    document.documentElement.innerHTML =
      '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>站点暂未开放</title><style>' + css + '</style></head>' +
      '<body><div class="koko-site-closed-wrap"><div class="koko-site-closed-card">' +
      '<div class="koko-site-closed-title">站点暂未开放</div>' +
      '<div class="koko-site-closed-msg"></div>' +
      '<div class="koko-site-closed-time">开放时间：' + openTime + ' - ' + closeTime + '</div>' +
      '</div></div></body>';

    var msgNode = document.querySelector('.koko-site-closed-msg');
    if (msgNode) msgNode.textContent = text;
  }

  async function boot() {
    try {
      var res = await fetch('/koko_usrvip_schedule_public.json?_=' + Date.now(), {
        cache: 'no-store'
      });

      if (!res.ok) return;

      var cfg = await res.json();

      var enabled = String(cfg.enabled || cfg.usrvip_site_schedule_enabled || '0') === '1';
      if (!enabled) return;

      var openTime = String(cfg.open_time || cfg.usrvip_site_open_time || '08:00');
      var closeTime = String(cfg.close_time || cfg.usrvip_site_close_time || '23:00');
      var message = String(cfg.message || cfg.usrvip_site_closed_message || '');

      var startMin = parseMinute(openTime);
      var endMin = parseMinute(closeTime);

      var now = new Date();
      var nowMin = now.getHours() * 60 + now.getMinutes();

      if (!isAllowed(nowMin, startMin, endMin)) {
        blockPage(message, openTime, closeTime);
      }
    } catch (e) {
      console.warn('[KOKO_USRVIP_ACCESS_GUARD_V1] load failed', e);
    }
  }

  boot();

  console.log('[KOKO_USRVIP_ACCESS_GUARD_V1] installed');
})();
