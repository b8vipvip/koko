/* Browser-free /usrvip recharge-history results regression: no external requests. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../usrvip/index.html'), 'utf8');
const start = html.indexOf('const KOKO_HISTORY_WAIT_LIMIT_MS = 8 * 60 * 1000;');
const end = html.indexOf('(function bindOrderIdExtractorMobileSafe()', start);
assert.ok(start > 0 && end > start, 'history query functions must exist');
const script = html.slice(start, end);

const query = { value: 'example-order-12345' };
const status = { hidden: false, textContent: '旧状态', innerHTML: '' };
const card = { innerHTML: '' };
const wrapper = { style: { display: 'none' } };
const hiddenCalls = [];
let apiResponse;
let fakeNow = Date.UTC(2026, 9, 28, 8, 51, 0); // Beijing: 2026-10-28 16:51:00.
const scheduled = new Map();
let nextTimerId = 0;
class FakeDate extends Date {
  static now() { return fakeNow; }
}
const elements = {
  query_phone: query, rechargeStatus: status,
  accountInfoOutside: card, accountInfoOutsideWrapper: wrapper,
};
function $(selector) {
  if (selector === '#query_phone') return { val: () => query.value };
  if (selector === '#accountInfoOutside') return { empty: () => { card.innerHTML = ''; } };
  if (selector === '#rechargeStatus') return {
    html: value => { status.innerHTML = value; status.textContent = value; },
    text: value => { status.textContent = value; status.innerHTML = ''; },
  };
  throw new Error('Unexpected jQuery selector: ' + selector);
}
$.get = (url, parameters, callback) => {
  assert.equal(url, '/get_recharge_status');
  assert.equal(parameters.q, query.value);
  callback(apiResponse);
  return { always(fn) { fn(); } };
};
const restores = [];
const win = {
  kokoHideInlineRechargeProgress: res => hiddenCalls.push(res.r_status),
  kokoRestoreQueriedRechargeProgress(res, q) {
    restores.push({order:res.order_id || q, id:res.tel_data_id});
    status.hidden = true;
    return true;
  },
};
const context = {
  window: win, document: { getElementById: id => elements[id] },
  $, api: x => x, layer: { msg: msg => { throw new Error(msg); } },
  console: { log() {} }, Object, Array, Date: FakeDate,
  setInterval(callback) {
    const id = ++nextTimerId;
    scheduled.set(id, callback);
    return id;
  },
  clearInterval(id) { scheduled.delete(id); },
  copyToClipboard() {},
};
vm.runInNewContext(script, context);

function run(response) {
  apiResponse = response;
  query.value = 'example-order-12345';
  context.checkRechargeStatus();
}
const meta = {
  status:'none', show_label:'手机号', show_value:'13000000000', vip_term:'月卡',
  recharge_time:'2026-10-27 20:15:27',
  accounts_24h:[{ nickname:'demo', userid:'user-demo', pic:'https://example.com/avatar.png' }],
};
for (const [raw, label, kind] of [
  ['成功', '充值成功', 'success'],
  ['充值失败', '充值失败', 'failure'],
  ['验证失效', '充值失败', 'failure'],
  ['超时', '充值超时', 'timeout'],
]) {
  status.hidden = false;
  run({ ...meta, r_status: raw });
  assert.equal(status.hidden, true, 'terminal result should hide separate status line');
  assert.match(card.innerHTML, new RegExp('koko-account-result-badge is-' + kind));
  assert.ok(card.innerHTML.includes(label));
  assert.ok(!card.innerHTML.includes('无新提交记录'));
  assert.ok(card.innerHTML.includes('user-demo'), 'account detail stays visible');
  assert.equal(wrapper.style.display, 'flex');
}
assert.equal(hiddenCalls.length, 4, 'terminal results should hide any cached progress');
assert.deepEqual(hiddenCalls, ['成功', '充值失败', '验证失效', '超时']);
run({status:'none', r_status:'', accounts_24h:[]});
assert.equal(status.hidden, false);
assert.match(status.innerHTML, /无新提交记录/);
assert.ok(!card.innerHTML.includes('koko-account-result-badge is-'));

// A historical tel_data order with NO terminal r_status is considered overdue
// only at 8 minutes since the Beijing-local server recharge_time.
const waiting = {
  ...meta, r_status:'开始充值', tel_data_id: 188,
  recharge_time:'2026-10-28 16:43:00',
};
fakeNow = Date.UTC(2026, 9, 28, 8, 50, 59);
run(waiting); // 7:59
assert.equal(status.hidden, true, 'ongoing formal query renders only the progress card');
assert.equal(restores.length, 1);
assert.equal(restores[0].id, 188);
assert.equal(card.innerHTML.includes('koko-account-result-badge is-timeout'), false);
assert.equal(scheduled.size, 1, 'a pending verified order should still be polled');

fakeNow = Date.UTC(2026, 9, 28, 8, 51, 0);
apiResponse = {...waiting};
// The next background refresh crosses the eight-minute threshold.
for (const callback of [...scheduled.values()]) callback();
assert.equal(status.hidden, true);
assert.equal(wrapper.style.display, 'flex');
assert.match(card.innerHTML, /koko-account-result-badge is-timeout/);
assert.ok(card.innerHTML.includes('充值超时'));
assert.equal(scheduled.size, 1, 'frontend-overdue result must keep checking server');

// The initial manual lookup after minute eight should also show timeout immediately.
run(waiting);
assert.match(card.innerHTML, /koko-account-result-badge is-timeout/);
assert.equal(scheduled.size, 1);

apiResponse = { ...waiting, r_status:'充值成功' };
// Simulate the next 30-second poll after the backend eventually reports success.
for (const callback of [...scheduled.values()]) callback();
assert.match(card.innerHTML, /koko-account-result-badge is-success/);
assert.ok(card.innerHTML.includes('充值成功'));
assert.equal(scheduled.size, 0, 'actual backend result should stop overtime polling');

// A missing or invalid recharge_time must NOT be called overdue.
run({...waiting, recharge_time:'not-a-date'});
assert.equal(status.hidden, false);
assert.equal(scheduled.size, 0);
run({...waiting, recharge_time:'2026-02-30 01:00:00'});
assert.equal(status.hidden, false);
run({...waiting, tel_data_id:null, recharge_time:'2026-10-01 16:43:00'});
assert.equal(status.hidden, false);
run({...waiting, r_status:'充值失败'});
assert.match(card.innerHTML, /koko-account-result-badge is-failure/);
assert.equal(scheduled.size, 0);
console.log('USRVIP history result: terminal precedence, 7:59/8:00 Beijing timeout, future outcome refresh passed');
