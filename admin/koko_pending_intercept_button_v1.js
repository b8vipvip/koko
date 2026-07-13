// KOKO_PENDING_INTERCEPT_BUTTON_V1
(function () {
  if (window.__KOKO_PENDING_INTERCEPT_BUTTON_V1__) return;
  window.__KOKO_PENDING_INTERCEPT_BUTTON_V1__ = true;

  var installing = false;
  var lastRecords = [];
  var lastFetchAt = 0;

  function msg(text) {
    if (window.layer && layer.msg) layer.msg(text);
    else alert(text);
  }

  function alertMsg(text) {
    if (window.layer && layer.alert) layer.alert(text);
    else alert(text);
  }

  function confirmMsg(text, yes) {
    if (window.layer && layer.confirm) {
      layer.confirm(text, { icon: 0, title: '确认操作' }, function (idx) {
        layer.close(idx);
        yes();
      });
    } else {
      if (confirm(text)) yes();
    }
  }

  function getSearchKeyword() {
    var selectors = [
      '#search_tel',
      '#searchTel',
      '#searchInput',
      'input[placeholder*="手机号或兑换码"]',
      'input[placeholder*="手机号"]',
      'input[placeholder*="兑换码"]'
    ];

    for (var i = 0; i < selectors.length; i++) {
      var el = document.querySelector(selectors[i]);
      if (el && typeof el.value === 'string') {
        return el.value.trim();
      }
    }

    return '';
  }

  function getCurrentPage() {
    var text = document.body.innerText || '';
    var m = text.match(/第\s*(\d+)\s*页/);
    if (m) return parseInt(m[1], 10) || 1;
    return 1;
  }

  function normalizeTime(v) {
    v = String(v || '').trim();

    // 已经是 06161542 这种显示格式
    if (/^\d{8}$/.test(v)) return v;

    // MySQL 日期：2026-06-16 15:42:04 -> 06161542
    var m = v.match(/^\d{4}-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/);
    if (m) return m[1] + m[2] + m[3] + m[4];

    return v.replace(/\D/g, '').slice(-8);
  }

  function recordTime(record) {
    return normalizeTime(record.create_date || record.created_at || record.time || '');
  }

  async function loadRecords(force) {
    var now = Date.now();
    if (!force && lastRecords.length && now - lastFetchAt < 1200) {
      return lastRecords;
    }

    var keyword = getSearchKeyword();
    var page = getCurrentPage();
    var url = '/api.php?action=search&tel=' + encodeURIComponent(keyword) + '&page=' + encodeURIComponent(page);

    try {
      var res = await fetch(url, { credentials: 'same-origin' });
      var json = await res.json();

      var records = json.records || json.data || json.rows || [];
      if (!Array.isArray(records)) records = [];

      lastRecords = records;
      lastFetchAt = now;
      return records;
    } catch (e) {
      console.warn('[KOKO_PENDING_INTERCEPT_BUTTON_V1] search load failed', e);
      return lastRecords || [];
    }
  }

  function findRecordForRow(row, records) {
    var tds = row.querySelectorAll('td');
    if (tds.length < 5) return null;

    var rowTime = normalizeTime(tds[0].innerText);
    var rowTel = (tds[1].innerText || '').trim();
    var rowAccount = (tds[2].innerText || '').trim();
    var rowPlan = (tds[3].innerText || '').trim();
    var rowStatus = (tds[4].innerText || '').trim();

    var candidates = records.filter(function (r) {
      var rTel = String(r.tel || r.phone || '').trim();
      var rStatus = String(r.r_status || r.status_text || r.status || '').trim();

      if (rTel !== rowTel) return false;
      if (rStatus !== rowStatus) return false;

      var rt = recordTime(r);
      if (rowTime && rt && rowTime !== rt) return false;

      return true;
    });

    if (candidates.length === 1) return candidates[0];

    // 时间匹配不到时，用手机号 + 待确认兜底
    candidates = records.filter(function (r) {
      return String(r.tel || r.phone || '').trim() === rowTel &&
             String(r.r_status || r.status_text || r.status || '').trim() === '待确认';
    });

    if (candidates.length === 1) return candidates[0];

    // 如果当前行 account/规格也能辅助匹配
    candidates = candidates.filter(function (r) {
      var acc = String(r.zhanghu || '').trim();
      var plan = String(r.pxtype || r.huiyuanguize || '').trim();

      if (rowAccount && acc && rowAccount !== acc) return false;
      if (rowPlan && plan && rowPlan !== 'null' && rowPlan !== plan) return false;

      return true;
    });

    return candidates[0] || null;
  }

  async function interceptTask(record, row) {
    if (!record || !record.id) {
      alertMsg('没有找到这行对应的任务 ID，请刷新后再试');
      return;
    }

    confirmMsg('确定要拦截这条待确认任务吗？', async function () {
      try {
        var res = await fetch('/api.php?action=check_and_update_c_status', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ id: record.id })
        });

        var json = {};
        try {
          json = await res.json();
        } catch (e) {}

        if (!res.ok || json.success === false) {
          throw new Error(json.message || '拦截失败');
        }

        var tds = row.querySelectorAll('td');
        if (tds[4]) {
          tds[4].innerHTML = '<span style="color:red;">已拦截</span>';
        }

        var opTd = tds[5] || row.lastElementChild;
        if (opTd) {
          opTd.innerHTML = '<button disabled style="background-color: grey;">拦截</button>';
        }

        msg('已拦截');
        lastFetchAt = 0;
      } catch (e) {
        alertMsg('拦截失败：' + e.message);
      }
    });
  }

  async function installButtons() {
    if (installing) return;
    installing = true;

    try {
      var tbody = document.querySelector('#data-table');
      if (!tbody) return;

      var records = await loadRecords(false);
      var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));

      rows.forEach(function (row) {
        var tds = row.querySelectorAll('td');
        if (tds.length < 5) return;

        var statusText = (tds[4].innerText || '').trim();
        if (statusText !== '待确认') return;

        var opTd = tds[5];
        if (!opTd) {
          opTd = document.createElement('td');
          row.appendChild(opTd);
        }

        var existing = opTd.querySelector('.koko-pending-intercept-btn');
        if (existing) return;

        var record = findRecordForRow(row, records);

        opTd.innerHTML = '';

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'koko-pending-intercept-btn';
        btn.textContent = '拦截';
        btn.style.cssText = 'background:#ff4d4f;color:#fff;border:0;border-radius:3px;padding:2px 6px;cursor:pointer;';

        btn.addEventListener('click', function () {
          interceptTask(record, row);
        });

        opTd.appendChild(btn);
      });
    } finally {
      installing = false;
    }
  }

  function boot() {
    installButtons();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  setInterval(installButtons, 800);

  var observer = new MutationObserver(function () {
    installButtons();
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  console.log('[KOKO_PENDING_INTERCEPT_BUTTON_V1] installed');
})();
