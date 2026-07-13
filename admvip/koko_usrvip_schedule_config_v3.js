// KOKO_USRVIP_SCHEDULE_CONFIG_UI_V3
(function () {
  if (window.__KOKO_USRVIP_SCHEDULE_CONFIG_UI_V3__) return;
  window.__KOKO_USRVIP_SCHEDULE_CONFIG_UI_V3__ = true;

  var API = '/phpapi/usrvip_site_schedule_config.php';
  var lastData = null;
  var userDirty = false;
  var uiFilledOnce = false;

  function q(id) {
    return document.getElementById(id);
  }

  function toast(msg) {
    if (window.layer && layer.msg) layer.msg(msg);
    else alert(msg);
  }

  function alertMsg(msg) {
    if (window.layer && layer.alert) layer.alert(msg);
    else alert(msg);
  }

  function markDirty() {
    userDirty = true;
  }

  async function loadConfig(forceFill) {
    try {
      var res = await fetch(API, { credentials: 'same-origin' });
      var json = await res.json();
      if (!json.success) throw new Error(json.message || '读取失败');

      lastData = json.data || {};

      // 用户已经手动点过/输入过时，不再自动覆盖
      if (forceFill || !userDirty) {
        fillUI();
      }
    } catch (e) {
      console.warn('[KOKO_USRVIP_SCHEDULE_CONFIG_UI_V3] load failed', e);
    }
  }

  function fillUI() {
    var d = lastData || {};

    if (q('koko_usrvip_site_schedule_enabled')) {
      q('koko_usrvip_site_schedule_enabled').checked = String(d.usrvip_site_schedule_enabled || '0') === '1';
    }

    if (q('koko_usrvip_site_close_time')) {
      q('koko_usrvip_site_close_time').value = d.usrvip_site_close_time || '23:00';
    }

    if (q('koko_usrvip_site_open_time')) {
      q('koko_usrvip_site_open_time').value = d.usrvip_site_open_time || '08:00';
    }

    if (q('koko_usrvip_site_closed_message')) {
      q('koko_usrvip_site_closed_message').value = d.usrvip_site_closed_message || '当前站点维护中，请稍后再试';
    }

    uiFilledOnce = true;
  }

  async function saveConfig(showTip) {
    if (!q('koko_usrvip_site_schedule_enabled')) return;

    var payload = {
      usrvip_site_schedule_enabled: q('koko_usrvip_site_schedule_enabled').checked ? 1 : 0,
      usrvip_site_close_time: q('koko_usrvip_site_close_time').value || '23:00',
      usrvip_site_open_time: q('koko_usrvip_site_open_time').value || '08:00',
      usrvip_site_closed_message: q('koko_usrvip_site_closed_message').value || ''
    };

    try {
      var res = await fetch(API, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      var json = await res.json();

      if (!res.ok || json.success === false) {
        throw new Error(json.message || '保存失败');
      }

      lastData = json.data || payload;
      userDirty = false;

      if (showTip) toast('usrvip 定时访问配置已保存');
    } catch (e) {
      alertMsg('usrvip 定时访问配置保存失败：' + e.message);
    }
  }

  function isVisible(el) {
    if (!el) return false;
    var rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function findSettingsModalContent() {
    var candidates = Array.prototype.slice.call(document.querySelectorAll(
      '.layui-layer-content, .layui-layer, .modal, .dialog, [role="dialog"]'
    ));

    for (var i = 0; i < candidates.length; i++) {
      var el = candidates[i];
      if (!isVisible(el)) continue;

      var t = String(el.innerText || el.textContent || '');

      if (
        t.indexOf('后端错误邮件通知') !== -1 &&
        t.indexOf('设备离线邮件通知') !== -1 &&
        t.indexOf('新充值任务邮件通知') !== -1
      ) {
        var content = el.querySelector('.layui-layer-content') || el;
        if (content && content.tagName !== 'BODY') return content;
      }
    }

    return null;
  }

  function removeWrongBodyBox() {
    Array.prototype.forEach.call(document.querySelectorAll('#koko_usrvip_schedule_config_box'), function (box) {
      var inLayer = !!box.closest('.layui-layer-content, .layui-layer, .modal, .dialog, [role="dialog"]');
      if (!inLayer) box.remove();
    });
  }

  function hookMainSave(container) {
    var layerBox = container.closest('.layui-layer') || container.parentElement || document;
    var buttons = Array.prototype.slice.call(layerBox.querySelectorAll('button, a, input[type="button"], input[type="submit"]'));

    buttons.forEach(function (btn) {
      var text = String(btn.innerText || btn.value || btn.textContent || '').trim();
      if (text === '保存' && !btn.__kokoUsrvipScheduleSaveHookedV3) {
        btn.__kokoUsrvipScheduleSaveHookedV3 = true;
        btn.addEventListener('click', function () {
          saveConfig(false);
        }, true);
      }
    });
  }

  function bindDirtyEvents() {
    [
      'koko_usrvip_site_schedule_enabled',
      'koko_usrvip_site_close_time',
      'koko_usrvip_site_open_time',
      'koko_usrvip_site_closed_message'
    ].forEach(function (id) {
      var el = q(id);
      if (!el || el.__kokoDirtyBoundV3) return;

      el.__kokoDirtyBoundV3 = true;
      el.addEventListener('change', markDirty, true);
      el.addEventListener('input', markDirty, true);
      el.addEventListener('click', markDirty, true);
    });
  }

  function insertUI() {
    removeWrongBodyBox();

    var content = findSettingsModalContent();
    if (!content) return;

    var exists = content.querySelector('#koko_usrvip_schedule_config_box');
    if (exists) {
      hookMainSave(content);
      bindDirtyEvents();

      // 关键：已存在时不要反复 fillUI，否则勾选会被旧数据覆盖
      if (!uiFilledOnce && lastData && !userDirty) {
        fillUI();
      }
      return;
    }

    content.style.maxHeight = '72vh';
    content.style.overflowY = 'auto';

    var wrap = document.createElement('div');
    wrap.id = 'koko_usrvip_schedule_config_box';
    wrap.style.cssText =
      'margin:18px 10px 0 10px;' +
      'padding:16px 12px 14px 12px;' +
      'border-top:1px solid #eee;' +
      'background:#fff;' +
      'box-sizing:border-box;';

    wrap.innerHTML =
      '<div style="font-weight:700;margin-bottom:10px;">usrvip 前端定时访问控制</div>' +

      '<label style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">' +
      '<input id="koko_usrvip_site_schedule_enabled" type="checkbox" style="width:auto;">' +
      '<span>开启定时关闭 usrvip 站点</span>' +
      '</label>' +

      '<div style="display:flex;gap:10px;margin-bottom:12px;">' +
      '<label style="flex:1;">关闭时间<br>' +
      '<input id="koko_usrvip_site_close_time" type="time" value="23:00" style="width:100%;box-sizing:border-box;padding:7px;border:1px solid #ddd;border-radius:4px;">' +
      '</label>' +
      '<label style="flex:1;">开启时间<br>' +
      '<input id="koko_usrvip_site_open_time" type="time" value="08:00" style="width:100%;box-sizing:border-box;padding:7px;border:1px solid #ddd;border-radius:4px;">' +
      '</label>' +
      '</div>' +

      '<label style="display:block;margin-bottom:6px;">关闭后页面提示文本</label>' +
      '<textarea id="koko_usrvip_site_closed_message" rows="4" style="width:100%;box-sizing:border-box;padding:8px;border:1px solid #ddd;border-radius:4px;" placeholder="当前站点维护中，请稍后再试"></textarea>' +

      '<div style="font-size:12px;color:#888;line-height:1.6;margin-top:8px;">' +
      '支持跨天时间，例如关闭 23:00，开启 08:00，表示每天 23:00 到第二天 08:00 关闭。' +
      '</div>' +

      '<button id="koko_usrvip_schedule_save_btn" type="button" style="margin-top:12px;padding:8px 12px;border:0;border-radius:4px;background:#1677ff;color:#fff;cursor:pointer;">保存访问设置</button>';

    content.appendChild(wrap);

    q('koko_usrvip_schedule_save_btn').addEventListener('click', function () {
      saveConfig(true);
    });

    bindDirtyEvents();
    hookMainSave(content);

    // 第一次插入时读取并填充
    uiFilledOnce = false;
    loadConfig(true);

    console.log('[KOKO_USRVIP_SCHEDULE_CONFIG_UI_V3] inserted into modal');
  }

  function boot() {
    insertUI();
    loadConfig(false);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  setInterval(insertUI, 500);

  var observer = new MutationObserver(function () {
    insertUI();
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true
  });
})();
