// Kiểm tra docs/js/advisor.js (tab 🧭 Tư vấn) + kurtosis/VaR cho ra cùng kết quả với quant_core (Python).
// Fixture do tools/make_web_fixture.py tạo. Chạy: node --test tests/web
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { enrich, assess, allocate, mood, PROFILES } from '../../docs/js/advisor.js';
import { kurtosis, valueAtRisk, pctChange } from '../../docs/js/indicators.js';

const fx = JSON.parse(readFileSync(new URL('./fixture.json', import.meta.url)));
const close = (a, b, rel = 1e-6, abs = 1e-9, msg = '') => {
  if (a == null || b == null || !Number.isFinite(a) || !Number.isFinite(b)) {
    assert.equal(Number.isFinite(a ?? NaN), Number.isFinite(b ?? NaN), `${msg}: ${a} vs ${b}`);
    return;
  }
  assert.ok(Math.abs(a - b) <= abs + rel * Math.abs(b), `${msg}: ${a} vs ${b}`);
};

let candles;
const items = [];
for (const c of fx.advisor) {
  if (c.candles) candles = c.candles;
  const cs = candles;
  test(`Tư vấn khớp advisor.assess (${c.kind}, ${c.profile})`, () => {
    const rows = enrich(cs, 50);
    rows.slice(-60).forEach((r, i) => {
      for (const k of ['emaSlow4h', 'roc7d', 'volAnn', 'volPct', 'dcHigh', 'ema200']) close(r[k], c.tail[i][k], 1e-7, 1e-9, `${k}[-${60 - i}]`);
    });
    const a = assess(`${c.kind.toUpperCase()}/USDT`, rows, { newsScore: c.news, capital: 1000, riskPct: PROFILES[c.profile].risk_pct, allowFutures: c.futures });
    if (c.profile === 'can_bang') items.push(a);
    const o = c.out;
    assert.equal(a.regime, o.regime); assert.equal(a.stance, o.stance); assert.equal(a.kind, o.kind); assert.equal(a.playbook, o.playbook);
    close(a.score, o.score, 1e-6, 1e-6, 'score');
    for (const k of Object.keys(o.factors)) close(a.factors[k], o.factors[k], 1e-6, 1e-9, `factor ${k}`);
    assert.equal(a.zone, o.zone);
    assert.deepEqual(a.reasons, o.reasons);
    if (o.plan == null) assert.equal(a.plan, null);
    else for (const k of ['stopLoss', 'takeProfit', 'positionUsd', 'riskUsd']) close(a.plan[k], o.plan[k], 1e-9, 1e-9, k);
    close(kurtosis(rows.map(r => r.logRet)), c.kurtosis, 1e-9, 1e-9, 'kurtosis');
    const [v, cv] = valueAtRisk(pctChange(rows.map(r => r.c)));
    close(v, c.var[0], 1e-9, 1e-12, 'VaR'); close(cv, c.var[1], 1e-9, 1e-12, 'CVaR');
  });
}

test('Phân bổ vốn + nhiệt kế khớp advisor.allocate / mood', () => {
  const alloc = allocate(items, 'mao_hiem', 1000);
  assert.equal(alloc.length, fx.allocate.length);
  alloc.forEach((r, i) => { assert.equal(r.asset, fx.allocate[i].asset); close(r.weight, fx.allocate[i].weight, 1e-9, 1e-12, 'weight'); });
  assert.deepEqual(mood(items.map(a => a.score)), fx.mood);
});
