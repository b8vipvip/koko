// KOKO_SYSTEM_SETTINGS_MOBILE_LAYOUT_V1
(function () {
  if (window.__KOKO_SYSTEM_SETTINGS_MOBILE_LAYOUT_V1__) return;
  window.__KOKO_SYSTEM_SETTINGS_MOBILE_LAYOUT_V1__ = true;

  function isMobileView() {
    return window.innerWidth <= 768 || /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent || '');
  }

  function isVisible(el) {
    if (!el) return false;
    var rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function isSystemSettingsLayer(layer) {
    if (!layer || !isVisible(layer)) return false;

    var title = layer.querySelector('.layui-layer-title');
    var titleText = title ? String(title.innerText || title.textContent || '') : '';
    var allText = String(layer.innerText || layer.textContent || '');

    return (
      titleText.indexOf('系统配置') !== -1 ||
      (
        allText.indexOf('后端错误邮件通知') !== -1 &&
        allText.indexOf('设备离线邮件通知') !== -1 &&
        allText.indexOf('新充值任务邮件通知') !== -1
      )
    );
  }

  function applyMobileLayout(layer) {
    if (!layer || !isMobileView()) return;

    var vh = window.innerHeight || document.documentElement.clientHeight || 700;
    var title = layer.querySelector('.layui-layer-title');
    var content = layer.querySelector('.layui-layer-content');
    var btn = layer.querySelector('.layui-layer-btn');

    layer.setAttribute('data-koko-mobile-layout', '1');

    layer.style.position = 'fixed';
    layer.style.left = '12px';
    layer.style.right = '12px';
    layer.style.top = '10px';
    layer.style.bottom = '10px';
    layer.style.width = 'auto';
    layer.style.height = (vh - 20) + 'px';
    layer.style.maxWidth = 'none';
    layer.style.maxHeight = 'none';
    layer.style.margin = '0';
    layer.style.transform = 'none';
    layer.style.display = 'flex';
    layer.style.flexDirection = 'column';
    layer.style.overflow = 'hidden';
    layer.style.borderRadius = '8px';
    layer.style.boxSizing = 'border-box';

    if (title) {
      title.style.flex = '0 0 auto';
      title.style.height = '48px';
      title.style.lineHeight = '48px';
      title.style.fontSize = '16px';
      title.style.boxSizing = 'border-box';
    }

    if (content) {
      content.style.flex = '1 1 auto';
      content.style.height = 'auto';
      content.style.maxHeight = 'none';
      content.style.overflowY = 'auto';
      content.style.overflowX = 'hidden';
      content.style.webkitOverflowScrolling = 'touch';
      content.style.boxSizing = 'border-box';
      content.style.paddingBottom = '18px';
    }

    if (btn) {
      btn.style.flex = '0 0 auto';
      btn.style.position = 'relative';
      btn.style.bottom = 'auto';
      btn.style.left = 'auto';
      btn.style.right = 'auto';
      btn.style.margin = '0';
      btn.style.padding = '10px 14px';
      btn.style.background = '#fff';
      btn.style.borderTop = '1px solid #eee';
      btn.style.boxSizing = 'border-box';
      btn.style.display = 'flex';
      btn.style.justifyContent = 'flex-end';
      btn.style.gap = '10px';
      btn.style.zIndex = '20';

      Array.prototype.forEach.call(btn.querySelectorAll('a, button, input'), function (b) {
        b.style.minWidth = '72px';
        b.style.height = '36px';
        b.style.lineHeight = '34px';
        b.style.textAlign = 'center';
        b.style.boxSizing = 'border-box';
        b.style.marginLeft = '0';
      });
    }

    var scheduleBox = layer.querySelector('#koko_usrvip_schedule_config_box');
    if (scheduleBox) {
      scheduleBox.style.margin = '18px 12px 0 12px';
      scheduleBox.style.padding = '16px 12px 14px 12px';
      scheduleBox.style.borderTop = '1px solid #eee';
      scheduleBox.style.background = '#fff';
      scheduleBox.style.boxSizing = 'border-box';
      scheduleBox.style.borderRadius = '6px';
      scheduleBox.style.borderRadius = '6px';
    }

    var textareas = layer.querySelectorAll('textarea');
    Array.prototype.forEach.call(textareas, function (ta) {
      ta.style.maxWidth = '100%';
      ta.style.boxSizing = 'border-box';
      ta.style.resize = 'vertical';
    });

    var timeInputs = layer.querySelectorAll('input[type="time"]');
    Array.prototype.forEach.call(timeInputs, function (inp) {
      inp.style.minWidth = '0';
      inp.style.boxSizing = 'border-box';
    });
  }

  function applyAll() {
    if (!isMobileView()) return;

    Array.prototype.forEach.call(document.querySelectorAll('.layui-layer'), function (layer) {
      if (isSystemSettingsLayer(layer)) {
        applyMobileLayout(layer);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyAll);
  } else {
    applyAll();
  }

  window.addEventListener('resize', function () {
    setTimeout(applyAll, 80);
  });

  window.addEventListener('orientationchange', function () {
    setTimeout(applyAll, 300);
  });

  setInterval(applyAll, 500);

  var observer = new MutationObserver(function () {
    applyAll();
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['style', 'class']
  });

  console.log('[KOKO_SYSTEM_SETTINGS_MOBILE_LAYOUT_V1] installed');
})();
