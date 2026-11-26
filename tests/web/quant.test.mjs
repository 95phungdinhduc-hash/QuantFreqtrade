// Kiểm tra web/js/quant.js cho ra cùng kết quả với bản Python (fixture do tools/make_web_fixture.py tạo).
// Chạy: node --test tests/web
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { addIndicators, adfPvalue, mackinnonP, planPosition, pickSignal, buildPlan, btcRegime, marketAllows } from '../../docs/js/quant.js';

const fx = JSON.parse(readFileSync(new URL('./fixture.json', import.meta.url)));

const close = (a, b, rel = 1e-6, abs = 1e-9, msg = '') => {
  if (a == null || b == null || !Number.isFinite(a) || !Number.isFinite(b)) {
    assert.equal(Number.isFinite(a ?? NaN), Number.isFinite(b ?? NaN), `${msg}: ${a} vs ${b}`);
    return;
  }
  assert.ok(Math.abs(a - b) <= abs + rel * Math.abs(b), `${msg}: ${a} vs ${b}`);
};

test('MacKinnon p-value khớp statsmodels', () => {
  for (const { t, p } of fx.mackinnon) close(mackinnonP(t), p, 1e-5, 1e-6, `t=${t}`);
});

test('ADF p-value khớp statsmodels.adfuller', () => {
  for (const { values, p } of fx.adf) close(adfPvalue(values), p, 1e-4, 1e-6, `n=${values.length}`);
});

for (const ds of fx.datasets) {
  test(`Chỉ báo khớp quant_core (${ds.kind})`, () => {
    const rows = addIndicators(ds.candles, { window: 50 });
    rows.forEach((r, i) => {
      const py = ds.rows[i];
      for (const k of ['mean', 'std', 'z', 'emaFast', 'emaSlow', 'gap', 'atr', 'rsi']) close(r[k], py[k], 1e-7, 1e-9, `${k}[${i}]`);
      close(r.adf, py.adf, 1e-4, 1e-6, `adf[${i}]`);
    });
  });

  test(`Tín hiệu nến cuối giống alert bot (${ds.kind})`, () => {
    const r = addIndicators(ds.candles, { window: 50 }).at(-1);
    const s = pickSignal(r);
    if (ds.signal == null) return assert.equal(s, null);
    assert.ok(ds.signal.strategy.toUpperCase().includes(s.strategy.toUpperCase()));
    for (const k of ['isLong', 'strong', 'slMult', 'tpMult', 'useMean', 'leverage']) assert.equal(s[k], ds.signal[k], k);
  });
}

test('pickSignal giống alert_bot.pick_signal', () => {
  for (const { row, out } of fx.signals) {
    const s = pickSignal({ ...row, adf: row.adf ?? NaN });
    if (out == null) { assert.equal(s, null, JSON.stringify(row)); continue; }
    assert.ok(out[0].toUpperCase().includes(s.strategy.toUpperCase()));
    assert.deepEqual([s.isLong, s.strong, s.slMult, s.tpMult, s.useMean, s.leverage], out.slice(1), JSON.stringify(row));
  }
});

test('planPosition giống risk.plan_position', () => {
  for (const { args, out } of fx.plans) {
    const p = planPosition({ capital: args.capital, riskPct: args.risk_pct, entry: args.entry, std: args.std,
                             mean: args.mean, isLong: args.is_long, slMult: args.sl_std_mult, tpMult: args.tp_std_mult,
                             minNotional: args.min_notional ?? 0 });
    for (const k of Object.keys(out)) close(p[k], out[k], 1e-12, 1e-12, k);
  }
});

test('buildPlan: Spot không Short, khối lượng không vượt vốn, Futures bị ép Min Notional', () => {
  const r = { c: 100, std: 0.5, mean: 101 };
  const long = buildPlan(r, { isLong: true, slMult: 2, tpMult: 1.5, useMean: true, leverage: 5 },
                         { capital: 100, riskPct: 2, minNotional: 300, maxLeverage: 3 });
  assert.equal(long.spot.usd, 100);          // lý tưởng 200 > vốn 100 -> giới hạn bằng vốn
  assert.ok(long.spot.capped);
  assert.equal(long.leverage, 3);            // trần đòn bẩy người dùng
  assert.ok(long.forcedMin && long.fplan.positionUsd === 300);
  const short = buildPlan(r, { isLong: false, slMult: 2, tpMult: 1.5, useMean: true, leverage: 2 },
                          { capital: 100, riskPct: 2 });
  assert.equal(short.spot, null);
});

test('Bộ lọc thị trường: BTC dưới SMA200 chỉ cho Short', () => {
  const days = Array.from({ length: 220 }, (_, i) => ({ t: i * 864e5, c: 100 + (i < 200 ? i : 400 - i * 1.5) }));
  const reg = btcRegime(days);
  assert.equal(reg.up, false);
  assert.equal(marketAllows(true, reg), false);
  assert.equal(marketAllows(false, reg), true);
  assert.equal(marketAllows(true, null), true);
  assert.equal(btcRegime(days.slice(0, 150)), null);
});
