// Run with: node tests/test_gui_buttons.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture(screen, reject = false) {
  const file = path.join(__dirname, '../src/gui/templates', screen + '.html');
  const script = fs.readFileSync(file, 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
  const nodes = {};
  const getNode = id => nodes[id] ||= {
    disabled: false, value: id.startsWith('default-') ? '7' : 'example.edu', handlers: {},
    addEventListener(name, fn) { this.handlers[name] = fn; },
  };
  const calls = [], alerts = [];
  const api = {};
  for (const method of ['select_host', 'save_settings', 'close_window']) {
    api[method] = value => {
      calls.push({ method, value });
      return reject ? Promise.reject(Error('test')) : Promise.resolve(true);
    };
  }
  vm.runInNewContext(script, {
    document: { getElementById: getNode, querySelector: () => null },
    window: { addEventListener() {}, pywebview: { api } },
    alert: message => alerts.push(message),
  });
  return { nodes, calls, alerts, click: id => getNode(id).handlers.click() };
}

(async () => {
  for (const screen of ['initial_setup', 'settings']) {
    const submit = screen === 'settings' ? 'save-btn' : 'submit-btn';
    const host = screen === 'settings' ? 'sakai-host' : 'host-input';
    let f = fixture(screen);
    f.click(submit); f.click(submit); f.click('cancel-btn');
    assert.equal(f.calls.length, 1);
    assert.equal(f.calls[0].method, screen === 'settings' ? 'save_settings' : 'select_host');
    assert.equal(f.nodes[submit].disabled, true);
    assert.equal(f.nodes['cancel-btn'].disabled, true);
    f = fixture(screen);
    f.click('cancel-btn'); f.click(submit); f.click('cancel-btn');
    assert.equal(f.calls.length, 1);
    assert.equal(f.calls[0].method, 'close_window');
    f = fixture(screen);
    f.nodes[host] = { value: '  ' };
    f.click(submit);
    assert.equal(f.calls.length, 0);
    assert.equal(f.nodes[submit].disabled, false);
    assert.equal(f.alerts.length, 1);
    for (const button of [submit, 'cancel-btn']) {
      f = fixture(screen, true);
      f.click(button);
      await Promise.resolve();
      assert.equal(f.nodes[submit].disabled, false);
      assert.equal(f.nodes['cancel-btn'].disabled, false);
      assert.equal(f.alerts.length, 1);
      f.click(button);
      assert.equal(f.calls.length, 2, 'retry must be possible after an API error');
      await Promise.resolve();
    }
    console.log('PASS: ' + screen + ' duplicate prevention, validation, error recovery');
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
