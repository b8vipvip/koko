/* Browser-free /usrvip recharge-history results regression: no external requests. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../usrvip/index.html'), 'utf8');
const start = html.indexOf('function kokoRechargeResultForDisplay(res) {');
const end = html.indexOf('(function bindOrderIdExtractorMobileSafe()', start);
assert.ok(start > 0 && end > start, 'history query functions must exist');
const script = html.slice(start, end);

const query = { value: 'example-order-12345' };
const status = { hidden: false, textContent: '旧状态', innerHTML: '' };
const card = { innerHTML: '' };
const wrapper = { style: { display: 'none' } };
const hiddenCalls = [];
let apiResponse;
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
};
const win = { kokoHideInlineRechargeProgress: res => hiddenCalls.push(res.r_status) };
const context = {
  window: win, document: { getElementById: id => elements[id] },
  $, api: x => x, layer: { msg: msg => { throw new Error(msg); } },
  console: { log() {} }, Object, Array,
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
console.log('USRVIP history result query: success/failure/timeout outrank status=none; passed');
