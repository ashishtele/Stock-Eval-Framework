import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { scoreCompany } from './score.mjs';

const example = JSON.parse(readFileSync(
  fileURLToPath(new URL('../assets/example.json', import.meta.url)), 'utf8'));

const clone = value => JSON.parse(JSON.stringify(value));

test('synthetic example reproduces the documented Model 1.0 arithmetic', () => {
  const result = scoreCompany(clone(example));
  assert.equal(result.modelVersion, '1.0');
  assert.equal(result.status, 'RESEARCH_SHORTLIST');
  assert.equal(result.score, 100);
  assert.equal(result.coveragePct, 100);
  assert.equal(result.evidenceStrengthPct, 100);
  assert.equal(result.portfolioStatus, 'NOT_ASSESSED');
  // Documented five-year base results (PDF section 2.8)
  assert.ok(Math.abs(result.valuation.base.terminalPrice - 248.832) < 1e-3);
  assert.ok(Math.abs(result.valuation.base.dividends - 44.6496) < 1e-3);
  assert.ok(Math.abs(result.valuation.base.terminalWealth - 293.4816) < 1e-3);
  assert.ok(Math.abs(result.valuation.base.fairValue - 172.0894) < 1e-3);
  assert.ok(Math.abs(result.valuation.base.marginOfSafety - 0.418907) < 1e-4);
  assert.ok(Math.abs(result.valuation.base.terminalWealthCagr - 0.24027) < 1e-4);
  // Bull P/E of 12 is capped at the current 10x P/E
  assert.equal(result.valuation.bull.effectiveTerminalPe, 10);
  // Zero modeled bear loss, but bear fair value is far below price
  assert.equal(result.valuation.bear.terminalWealthLoss, 0);
  assert.ok(Math.abs(result.valuation.bear.fairValue - 74.7666) < 1e-3);
});

test('empty G1 evidence list drops score to 90 and blocks shortlisting', () => {
  const input = clone(example);
  input.evidence.G1 = [];
  const result = scoreCompany(input);
  assert.equal(result.score, 90);
  assert.equal(result.status, 'INSUFFICIENT_EVIDENCE');
  assert.ok(result.reasons.some(reason => reason.includes('G1')));
});

test('a failed gate vetoes even a perfect score', () => {
  const input = clone(example);
  input.gates.auditIntegrity = {
    status: 'fail',
    sourceIds: ['annual'],
    checkedAt: '2026-11-12',
    note: 'Synthetic fail: unresolved adverse audit opinion.',
  };
  const result = scoreCompany(input);
  assert.equal(result.score, 100);
  assert.equal(result.status, 'REJECT_NEW_POSITION');
});

test('non-financial sectorClass is required; anything else is OUT_OF_SCOPE', () => {
  const input = clone(example);
  input.sectorClass = 'financial';
  const result = scoreCompany(input);
  assert.equal(result.status, 'OUT_OF_SCOPE');
  assert.equal(result.score, null);
});
