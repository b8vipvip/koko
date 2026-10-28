/* Node-only simulated DOM regression. Does not call real SMS, login, or exchange APIs. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../usrvip/index.html'), 'utf8');
const section = html.split('<!-- KOKO_RECHARGE_6MIN_PROGRESS_V1_START -->')[1]
  .split('<!-- KOKO_RECHARGE_6MIN_PROGRESS_V1_END -->')[0];
const script = section.match(/<script>([\s\S]*?)<\/script>/)[1];

let time = 1_000_000;
const start = time;
const saved = new Map();
const storage = {
  getItem: (key) => saved.get(key) || null,
  setItem: (key, value) => saved.set(key, String(value)),
  removeItem: key => saved.delete(key),
};
const $ = {
  get: () => ({ always: () => {} }), // Do not touch external backends.
};
const mkEl = () => ({ textContent: '', style: {} });
const bar = mkEl();
const percent = mkEl();
const elapsed = mkEl();
const side = {
  textContent: '',
  classes: new Set(),
  classList: { toggle(name, on) {
    if (on) side.classes.add(name);
    else side.classes.delete(name);
  } },
};
const status = {
  textContent: '',
  _html: '',
  dataset: {},
  parentNode: null,
  set innerHTML(value) {
    this._html = value;
    this.textContent = String(value).replace(/<[^>]*>/g, '');
  },
  get innerHTML() { return this._html; },
};
const textRegion = {
  appendChild(element) { element.parentNode = this; },
};
const nodes = {
  '.koko-recharge-progress-bar': bar,
  '.koko-recharge-progress-percent': percent,
  '.koko-recharge-progress-elapsed': elapsed,
  '.koko-recharge-progress-countdown': side,
  '.koko-recharge-progress-text': textRegion,
};
const root = {
  querySelector: (selector) => nodes[selector] || null,
  contains: (element) => element.parentNode === textRegion,
};
const slot = {
  hidden: true,
  contains: element => element.parentNode === textRegion,
  parentNode: {
    insertBefore(element) { element.parentNode = this; },
  },
  _html: '',
  querySelector: (selector) => selector === '[data-koko-recharge-progress="1"]' && slot._html ? root : null,
  set innerHTML(value) { this._html = value; },
  get innerHTML() { return this._html; },
  scrollIntoView() {},
};
const document = {
  readyState: 'loading',
  addEventListener() {},
  getElementById(id) {
    return id === 'kokoRechargeInline' ? slot :
      id === 'rechargeStatus' ? status : null;
  },
  querySelectorAll() { return slot._html ? [root] : []; },
};
const window = {};
vm.runInNewContext(script, {
  window, document, localStorage: storage, $, api: (url) => url,
  Date: { now: () => time }, Math, JSON,
  setInterval: () => 1, clearInterval: () => {},
});

// No progress when a formal exchange task has not been created.
window.kokoShowInlineRechargeProgress(false);
assert.equal(slot.hidden, true);

saved.set('koko_recharge_6min_progress_v1', JSON.stringify({
  startAt: start, order_id: 'dummy', record_id: 88, tel_data_id: 123,
  statusChecking: true, finalStatus: '',
}));

time = start + 7 * 60_000;
window.kokoShowInlineRechargeProgress(false);
assert.equal(slot.hidden, false);
assert.equal(status.parentNode, textRegion, 'status node must be moved into the card');
assert.equal(side.textContent, '充值中');
assert.equal(elapsed.textContent, '已提交：7分钟');
assert.match(status.textContent, /6分钟/);
assert.ok(!slot.innerHTML.includes('koko-recharge-progress-tip'));
assert.equal(html.includes('id="rechargeResult"'), false);
assert.ok(Number(percent.textContent.replace('%', '')) < 100);

time = start + 8 * 60_000 - 1;
window.kokoShowInlineRechargeProgress(false);
assert.equal(side.textContent, '充值中', '8 min warning must not trigger prematurely');

time = start + 8 * 60_000;
window.kokoShowInlineRechargeProgress(false);
assert.equal(side.textContent, '充值超时，请联系客服');
assert.ok(side.classes.has('is-timeout'));
assert.match(status.textContent, /已等待超过8分钟/);
assert.ok(Number(percent.textContent.replace('%', '')) < 100,
  'frontend timeout must not mark progress complete');

saved.set('koko_recharge_6min_progress_v1', JSON.stringify({
  startAt: start, order_id: 'dummy', record_id: 88, tel_data_id: 123,
  statusChecking: false, finalStatus: '充值成功', finalResult: '充值成功',
}));
window.kokoShowInlineRechargeProgress(false);
assert.equal(side.textContent, '充值成功', 'real backend result overrides UI timeout');
assert.equal(percent.textContent, '100%');
assert.match(status.textContent, /充值结果：充值成功/);


window.kokoHideInlineRechargeProgress({ order_id:'dummy', r_status:'成功' });
assert.equal(slot.hidden, true);
assert.equal(slot.innerHTML, '');
assert.equal(status.hidden, true);
assert.equal(saved.has('koko_recharge_6min_progress_v1'), false,
  'finished matched-order progress must not reappear on reload');

window.kokoSaveRechargeProgressState({
  startAt:time, order_id:'another-order', record_id:99, tel_data_id:999,
  finalStatus:'', finalResult:'', finishedAt:null,
});
window.kokoShowInlineRechargeProgress(true);
assert.equal(slot.hidden, false);
assert.equal(status.hidden, false);

console.log('USRVIP simulated DOM: pending/timeout/final/switch to history/new submission passed');
