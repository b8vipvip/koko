/* Verify 30s spinner countdown using a mocked /submit; no real network or OTP. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../usrvip/index.html'), 'utf8');
const start = html.indexOf('function submitUserInfo() {');
const end = html.indexOf('function showAccountPopup(accounts) {', start);
assert.ok(start > 0 && end > start);
const code = html.slice(start, end);
const fields = { '#phone':'13000000000', '#code':'123456', '#order_id':'example1234' };
let timer = null;
let time = 2_000_000;
let popup = '';
let closed = 0;
let submitUrl = '';
let settleFetch;
const countdown = { textContent: '' };
const input = selector => ({
  val(value) {
    if (value !== undefined) { fields[selector] = value; return this; }
    return fields[selector];
  },
  prop() { return this; }, css() { return this; },
});
const context = {
  Date: { now: () => time },
  Math, JSON,
  window: {},
  inFlightSubmit: false,
  document: { getElementById: key => key === 'koko-submit-loading-countdown' ? countdown : null },
  $: input,
  layer: {
    open(config) { popup = config.content; return 42; },
    close(index) { assert.equal(index, 42); closed++; },
    msg(message) { throw new Error('Unexpected validation: ' + message); },
    alert() {},
  },
  setInterval(callback, rate) { assert.equal(rate, 250); timer = callback; return 17; },
  clearInterval(index) { assert.equal(index, 17); timer = null; },
  api: x => x,
  genIdemKey: () => 'test-idempotency-key',
  fetch(url, options) {
    submitUrl = url;
    assert.equal(options.method, 'POST');
    return new Promise(resolve => { settleFetch = resolve; });
  },
  console: { error() {} },
};
vm.runInNewContext(code, context);
context.submitUserInfo();
assert.equal(submitUrl, '/submit');
assert.match(popup, /koko-submit-loading-spinner/);
assert.match(popup, /koko-submit-loading-rotate/);
assert.match(popup, /koko-submit-loading-countdown/);
assert.equal(countdown.textContent, '30s');
time += 9000; timer(); assert.equal(countdown.textContent, '21s');
time += 20000; timer(); assert.equal(countdown.textContent, '1s');
time += 1000; timer(); assert.equal(countdown.textContent, '0s');
assert.equal(timer, null, 'Countdown ends but must not cancel pending /submit request');
assert.equal(closed, 0, 'The loading popup must remain open while backend is running');

async function run(){
  settleFetch({ok:true, json: async()=>({ status:'new_user' })});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(closed, 1, 'The popup closes when the real request finishes');
  assert.equal(timer, null);
  console.log('USRVIP loading countdown: 30,21,1,0 then keep pending until response; passed');
}
run().catch(err=>{console.error(err);process.exitCode=1;});
