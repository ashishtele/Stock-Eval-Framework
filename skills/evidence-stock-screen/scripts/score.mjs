import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

// Evidence Stock Screen calculator — Model 1.0 (12 Nov 2026).
// Deterministic, dependency-free JSON-to-score implementation.
// Reconstructed from the "Evidence Stock Screen" PDF export (section 4).
export const METRICS = [
  { id: 'G1', pillar: 'Governance', label: 'Commitment delivery', weight: 10, bad: 0.5, good: 0.9 },
  { id: 'G2', pillar: 'Governance', label: 'Cash conversion', weight: 8, bad: 0.5, good: 1 },
  { id: 'G3', pillar: 'Governance', label: 'Promoter pledge percentage', weight: 4, bad: 20, good: 0 },
  { id: 'G4', pillar: 'Governance', label: 'Related-party sales percentage', weight: 3, bad: 20, good: 5 },
  { id: 'B1', pillar: 'Business', label: 'Three-year mean ROCE', weight: 10, bad: 0.1, good: 0.2 },
  { id: 'B2', pillar: 'Business', label: 'Operating-margin retention', weight: 5, bad: 0.7, good: 1 },
  { id: 'B3', pillar: 'Business', label: 'Largest-customer percentage', weight: 5, bad: 40, good: 10 },
  { id: 'F1', pillar: 'Finances', label: 'Net debt / EBITDA', weight: 6, bad: 3, good: 0 },
  { id: 'F2', pillar: 'Finances', label: 'Interest coverage', weight: 6, bad: 2, good: 8 },
  { id: 'F3', pillar: 'Finances', label: 'Positive-FCF years out of five', weight: 5, bad: 1, good: 4 },
  { id: 'F4', pillar: 'Finances', label: 'Three-year diluted-share CAGR', weight: 3, bad: 0.05, good: 0 },
  { id: 'R1', pillar: 'Runway', label: 'Three-year revenue CAGR', weight: 5, bad: 0.05, good: 0.15 },
  { id: 'R2', pillar: 'Runway', label: 'Incremental pre-tax capital return', weight: 5, bad: 0.1, good: 0.2 },
  { id: 'R3', pillar: 'Runway', label: 'Verified runway checks out of four', weight: 5, bad: 0, good: 4 },
  { id: 'V1', pillar: 'Valuation', label: 'Base margin of safety', weight: 10, bad: 0, good: 0.3 },
  { id: 'V2', pillar: 'Valuation', label: 'Base terminal-wealth CAGR', weight: 5, bad: 0.1, good: 0.2 },
  { id: 'D1', pillar: 'Downside', label: 'Bear terminal-wealth loss', weight: 5, bad: 0.5, good: 0.15 },
];
const SOURCE_QUALITY = { audited: 1, regulator: 1, exchange: 1, management: 0.8, secondary: 0.5, podcast: 0 };
const GATES = ['auditIntegrity', 'reportingIntegrity', 'solvency', 'filingCurrency', 'liquidity'];
const CRITICAL = ['G1', 'G2', 'B1', 'F1', 'F2', 'V1', 'V2', 'D1'];
const DAY = 86400000;

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}

function dateValue(value, label) {
  requireCondition(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value), `${label} must be YYYY-MM-DD`);
  const parsed = Date.parse(`${value}T00:00:00Z`);
  requireCondition(Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 10) === value,
    `${label} is not a real date`);
  return parsed;
}

function numberValue(value, label, min = -Infinity, max = Infinity) {
  if (value === null || value === undefined) return null;
  requireCondition(typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max,
    `${label} must be a finite number in [${min}, ${max}], or null`);
  return value;
}

function present(values) {
  return values.every(value => typeof value === 'number' && Number.isFinite(value));
}

function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function sumField(rows, field) {
  return present(rows.map(row => row[field])) ? rows.reduce((total, row) => total + row[field], 0) : null;
}

function growth(latest, earlier) {
  return present([latest, earlier]) && latest > 0 && earlier > 0 ? (latest / earlier) ** (1 / 3) - 1 : null;
}

function rounded(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function evidenceQuality(ids, sources) {
  if (!ids || ids.length === 0) return 0;
  requireCondition(Array.isArray(ids), 'Evidence references must be arrays of source IDs');
  return Math.min(...ids.map(id => {
    requireCondition(sources.has(id), `Unknown source ID: ${id}`);
    return SOURCE_QUALITY[sources.get(id).kind];
  }));
}

function validateSources(input, asOf) {
  requireCondition(Array.isArray(input.sources), 'sources must be an array');
  const sources = new Map();
  for (const source of input.sources) {
    requireCondition(typeof source.id === 'string' && source.id.length > 0 && !sources.has(source.id),
      'Source IDs must be nonempty and unique');
    requireCondition(Object.hasOwn(SOURCE_QUALITY, source.kind), `Unknown source kind: ${source.kind}`);
    requireCondition(typeof source.locator === 'string' && source.locator.trim().length > 0,
      'Every source requires a page, section or table locator');
    const url = new URL(source.url);
    requireCondition(['http:', 'https:'].includes(url.protocol), 'Sources must have HTTP(S) URLs');
    requireCondition(input.synthetic || !url.hostname.endsWith('.invalid'),
      'Synthetic URLs cannot support real-company research');
    requireCondition(dateValue(source.publishedAt, 'Source publishedAt') <= asOf,
      'Source publishedAt must not exceed asOf');
    requireCondition(dateValue(source.accessedAt, 'Source accessedAt') >= dateValue(source.publishedAt,
      'Source publishedAt'), 'Source accessedAt must not precede publication');
    sources.set(source.id, source);
  }
  return sources;
}

function calculateValuation(valuation, revenueGrowth) {
  if (!present([valuation.price, valuation.normalizedEps, valuation.discountRate, valuation.peerMedianPe,
    valuation.historyMedianPe, revenueGrowth]) || valuation.normalizedEps <= 0) return null;
  const scenarios = valuation.scenarios;
  if (!scenarios || !['bear', 'base', 'bull'].every(name => scenarios[name] &&
      present([scenarios[name].epsGrowth, scenarios[name].terminalPe, scenarios[name].payoutRatio]))) return null;
  requireCondition(scenarios.base.epsGrowth <= Math.min(0.2, Math.max(0, revenueGrowth)) + 1e-10,
    'Base growth exceeds the lower of historical revenue growth and 20%');
  requireCondition(scenarios.bear.epsGrowth <= scenarios.base.epsGrowth &&
    scenarios.base.epsGrowth <= scenarios.bull.epsGrowth,
    'Scenario growth must be ordered bear <= base <= bull');
  requireCondition(scenarios.bear.terminalPe <= scenarios.base.terminalPe &&
    scenarios.base.terminalPe <= scenarios.bull.terminalPe,
    'Scenario terminal P/E must be ordered bear <= base <= bull');
  const ceiling = Math.min(valuation.price / valuation.normalizedEps, valuation.peerMedianPe,
    valuation.historyMedianPe);
  const result = {};
  for (const name of ['bear', 'base', 'bull']) {
    const scenario = scenarios[name];
    const effectiveTerminalPe = Math.min(scenario.terminalPe, ceiling);
    let dividends = 0;
    let discountedDividends = 0;
    for (let year = 1; year <= 5; year += 1) {
      const dividend = valuation.normalizedEps * (1 + scenario.epsGrowth) ** year * scenario.payoutRatio;
      dividends += dividend;
      discountedDividends += dividend / (1 + valuation.discountRate) ** year;
    }
    const terminalPrice = valuation.normalizedEps * (1 + scenario.epsGrowth) ** 5 * effectiveTerminalPe;
    const terminalWealth = terminalPrice + dividends;
    const fairValue = terminalPrice / (1 + valuation.discountRate) ** 5 + discountedDividends;
    result[name] = {
      effectiveTerminalPe,
      fairValue,
      terminalPrice,
      dividends,
      terminalWealth,
      terminalWealthCagr: (terminalWealth / valuation.price) ** 0.2 - 1,
      marginOfSafety: 1 - valuation.price / fairValue,
      terminalWealthLoss: Math.max(0, 1 - terminalWealth / valuation.price),
    };
    requireCondition(Object.values(result[name]).every(Number.isFinite),
      'Valuation arithmetic overflow or invalid result');
  }
  requireCondition(result.bear.terminalWealth <= result.base.terminalWealth &&
    result.base.terminalWealth <= result.bull.terminalWealth,
    'Scenario terminal wealth must be ordered bear <= base <= bull');
  return result;
}

export function scoreCompany(input) {
  requireCondition(input && typeof input === 'object', 'Input must be an object');
  requireCondition(input.schemaVersion === '1.0', 'schemaVersion must be 1.0');
  requireCondition(typeof input.company === 'string' && input.company.trim().length > 0, 'company is required');
  requireCondition(typeof input.synthetic === 'boolean', 'synthetic must be true or false');
  const asOf = dateValue(input.asOf, 'asOf');
  if (input.sectorClass !== 'non-financial') {
    return {
      company: input.company,
      asOf: input.asOf,
      modelVersion: '1.0',
      status: 'OUT_OF_SCOPE',
      score: null,
      reasons: ['Use a separate sector model for financial companies or unsupported classifications.'],
    };
  }
  const sources = validateSources(input, asOf);
  requireCondition(input.evidence && typeof input.evidence === 'object', 'evidence is required');
  for (const [id, sourceIds] of Object.entries(input.evidence)) {
    requireCondition(METRICS.some(metric => metric.id === id), `Unknown metric ID: ${id}`);
    evidenceQuality(sourceIds, sources);
  }
  const rows = input.financials;
  requireCondition(Array.isArray(rows) && rows.length === 5,
    'Exactly five consecutive annual financial periods are required');
  for (const [index, row] of rows.entries()) {
    const yearEnd = dateValue(row.yearEnd, 'yearEnd');
    requireCondition(yearEnd <= asOf, 'Financial periods must not exceed asOf');
    if (index > 0) {
      const gap = (yearEnd - dateValue(rows[index - 1].yearEnd, 'yearEnd')) / DAY;
      requireCondition(gap >= 350 && gap <= 380,
        'Financial periods must be consecutive, chronological 12-month years');
    }
    for (const field of ['revenue', 'ebit', 'ebitda', 'pat', 'cfo', 'capex', 'capitalEmployed', 'netDebt',
      'interest', 'dilutedShares']) {
      numberValue(row[field], `${row.yearEnd}.${field}`,
        ['revenue', 'capex', 'interest', 'dilutedShares'].includes(field) ? 0 : -Infinity);
    }
  }
  const business = input.business;
  requireCondition(business && typeof business === 'object', 'business is required');
  for (const field of ['promoterPledgePct', 'relatedPartySalesPct', 'largestCustomerPct'])
    numberValue(business[field], field, 0, 100);
  for (const field of ['dueCommitments', 'deliveredCommitments']) {
    const value = numberValue(business[field], field, 0);
    requireCondition(value === null || Number.isInteger(value), `${field} must be an integer`);
  }
  if (present([business.dueCommitments, business.deliveredCommitments]))
    requireCondition(business.deliveredCommitments <= business.dueCommitments,
      'Delivered commitments cannot exceed due commitments');
  requireCondition(Array.isArray(business.runwayChecks) && business.runwayChecks.length === 4 &&
    business.runwayChecks.every(value => value === null || typeof value === 'boolean'),
    'runwayChecks requires four boolean-or-null entries');
  const valuationInput = input.valuation;
  requireCondition(valuationInput && typeof valuationInput === 'object', 'valuation is required');
  for (const field of ['price', 'normalizedEps', 'discountRate', 'peerMedianPe', 'historyMedianPe']) {
    numberValue(valuationInput[field], field,
      field === 'normalizedEps' ? -Infinity : Number.MIN_VALUE,
      field === 'discountRate' ? 1 : Infinity);
  }
  const priceDate = valuationInput.priceDate == null ? null : dateValue(valuationInput.priceDate, 'priceDate');
  requireCondition(priceDate === null || priceDate <= asOf, 'priceDate must not exceed asOf');
  for (const name of ['bear', 'base', 'bull']) {
    const scenario = valuationInput.scenarios?.[name];
    if (!scenario) continue;
    numberValue(scenario.epsGrowth, `${name}.epsGrowth`, -0.99, name === 'bull' ? 0.3 : 0.2);
    numberValue(scenario.terminalPe, `${name}.terminalPe`, Number.MIN_VALUE);
    numberValue(scenario.payoutRatio, `${name}.payoutRatio`, 0, 1);
  }
  const latest = rows[4];
  const trailing = rows.slice(2);
  const totalPat = sumField(trailing, 'pat');
  const totalCfo = sumField(trailing, 'cfo');
  const revenueGrowth = growth(latest.revenue, rows[1].revenue);
  const valuation = calculateValuation(valuationInput, revenueGrowth);
  const roceInputs = rows.slice(1).flatMap(row => [row.capitalEmployed]).concat(trailing.map(row => row.ebit));
  const roce = !present(roceInputs) ? null
    : rows.slice(1).some(row => row.capitalEmployed <= 0) ? 0
      : mean(trailing.map((row, index) =>
        row.ebit / ((row.capitalEmployed + rows[index + 1].capitalEmployed) / 2)));
  const margins = rows.map(row =>
    present([row.ebit, row.revenue]) && row.revenue > 0 ? row.ebit / row.revenue : null);
  const medianMargin = present(margins) ? [...margins].sort((left, right) => left - right)[2] : null;
  const incrementalInputs = [latest.ebit, rows[1].ebit, latest.capitalEmployed, rows[1].capitalEmployed];
  const values = {
    G1: present([business.dueCommitments, business.deliveredCommitments]) && business.dueCommitments >= 5
      ? business.deliveredCommitments / business.dueCommitments : null,
    G2: present([totalPat, totalCfo]) ? totalPat > 0 ? totalCfo / totalPat : 0 : null,
    G3: business.promoterPledgePct ?? null,
    G4: business.relatedPartySalesPct ?? null,
    B1: roce,
    B2: medianMargin === null ? null : medianMargin <= 0 ? 0 : Math.min(...margins.slice(2)) / medianMargin,
    B3: business.largestCustomerPct ?? null,
    F1: present([latest.netDebt, latest.ebitda]) ? latest.ebitda > 0 ? latest.netDebt / latest.ebitda : 3 : null,
    F2: present([latest.ebit, latest.interest]) ? latest.ebit <= 0 ? 0 : latest.interest === 0 ? 8
      : latest.ebit / latest.interest : null,
    F3: rows.every(row => present([row.cfo, row.capex]))
      ? rows.filter(row => row.cfo - row.capex > 0).length : null,
    F4: growth(latest.dilutedShares, rows[1].dilutedShares),
    R1: revenueGrowth,
    R2: present(incrementalInputs) && latest.capitalEmployed > rows[1].capitalEmployed &&
      rows[1].capitalEmployed > 0
      ? (latest.ebit - rows[1].ebit) / (latest.capitalEmployed - rows[1].capitalEmployed) : null,
    R3: business.runwayChecks.some(value => value === null) ? null
      : business.runwayChecks.filter(Boolean).length,
    V1: valuation?.base.marginOfSafety ?? null,
    V2: valuation?.base.terminalWealthCagr ?? null,
    D1: valuation?.bear.terminalWealthLoss ?? null,
  };
  requireCondition(Object.values(values).every(value => value === null || Number.isFinite(value)),
    'Financial arithmetic overflow or invalid result');
  const metrics = METRICS.map(metric => {
    const value = values[metric.id];
    const quality = value === null ? 0 : evidenceQuality(input.evidence[metric.id], sources);
    const normalized = value === null ? 0
      : Math.max(0, Math.min(1, (value - metric.bad) / (metric.good - metric.bad)));
    return {
      ...metric,
      value,
      normalized,
      quality,
      points: metric.weight * normalized * quality,
      sourceIds: input.evidence[metric.id] ?? [],
      missing: value === null || quality === 0,
    };
  });
  const score = metrics.reduce((total, metric) => total + metric.points, 0);
  const coverage = metrics.reduce((total, metric) => total + (metric.quality >= 0.8 ? metric.weight : 0), 0);
  const evidenceStrength = metrics.reduce((total, metric) => total + metric.weight * metric.quality, 0);
  const gates = GATES.map(name => {
    const gate = input.gates?.[name] ?? { status: 'unknown', sourceIds: [] };
    requireCondition(['pass', 'fail', 'unknown'].includes(gate.status), `Invalid gate status: ${name}`);
    const quality = evidenceQuality(gate.sourceIds, sources);
    const checkedAt = gate.checkedAt == null ? null : dateValue(gate.checkedAt, `${name}.checkedAt`);
    requireCondition(checkedAt === null || checkedAt <= asOf, `${name}.checkedAt must not exceed asOf`);
    const supported = quality === 1 && checkedAt !== null && (asOf - checkedAt) / DAY <= 30 &&
      typeof gate.note === 'string' && gate.note.trim().length > 0;
    return {
      name,
      declaredStatus: gate.status,
      effectiveStatus: gate.status === 'pass' && !supported ? 'unknown' : gate.status,
      quality,
      sourceIds: gate.sourceIds ?? [],
      note: gate.note ?? '',
    };
  });
  const reasons = [];
  const failed = gates.filter(gate => gate.effectiveStatus === 'fail');
  const unknown = gates.filter(gate => gate.effectiveStatus === 'unknown');
  const risks = [];
  if (present([totalPat]) && totalPat <= 0) risks.push('Non-positive three-year aggregate profit.');
  if (rows.slice(1).some(row => row.capitalEmployed !== null && row.capitalEmployed <= 0))
    risks.push('Non-positive capital employed makes ordinary ROCE unsuitable.');
  if (present([latest.ebitda]) && latest.ebitda <= 0) risks.push('Non-positive EBITDA.');
  if (values.F1 !== null && values.F1 > 3) risks.push('Net debt / EBITDA exceeds 3.');
  if (values.F2 !== null && values.F2 < 2) risks.push('Interest coverage below 2.');
  if (values.G3 !== null && values.G3 > 20) risks.push('Promoter pledge exceeds 20%.');
  if (present([valuationInput.normalizedEps]) && valuationInput.normalizedEps <= 0)
    risks.push('Non-positive normalized EPS; earnings-multiple model unsuitable.');
  if (values.D1 !== null && values.D1 > 0.5) risks.push('Modeled bear terminal-wealth loss exceeds 50%.');
  const freshness = [];
  if (priceDate === null || (asOf - priceDate) / DAY > 7)
    freshness.push('Price missing or more than 7 calendar days old.');
  if ((asOf - dateValue(latest.yearEnd, 'latest yearEnd')) / DAY > 550)
    freshness.push('Latest annual financial period is more than 550 days old.');
  const missingCritical = metrics.filter(metric => CRITICAL.includes(metric.id) && metric.quality < 0.8);
  if (failed.length) reasons.push(`Failed gates: ${failed.map(gate => gate.name).join(', ')}.`);
  reasons.push(...risks);
  if (unknown.length) reasons.push(`Unresolved gates: ${unknown.map(gate => gate.name).join(', ')}.`);
  reasons.push(...freshness);
  if (missingCritical.length)
    reasons.push(`Missing or weak critical evidence: ${missingCritical.map(metric => metric.id).join(', ')}.`);
  if (coverage < 85) reasons.push('Weighted primary/management evidence coverage below 85%.');
  if (evidenceStrength < 80) reasons.push('Weighted evidence strength below 80%.');
  let status;
  if (failed.length) status = 'REJECT_NEW_POSITION';
  else if (risks.length) status = 'HIGH_RISK';
  else if (unknown.length || freshness.length || missingCritical.length || coverage < 85 || evidenceStrength < 80)
    status = 'INSUFFICIENT_EVIDENCE';
  else if (score >= 75 && values.V1 >= 0.2 && values.V2 >= valuationInput.discountRate && values.D1 <= 0.35)
    status = 'RESEARCH_SHORTLIST';
  else if (score >= 60) status = 'WATCHLIST';
  else status = 'LOW_PRIORITY';
  const pillars = {};
  for (const metric of metrics) pillars[metric.pillar] = (pillars[metric.pillar] ?? 0) + metric.points;
  return {
    modelVersion: '1.0',
    company: input.company,
    asOf: input.asOf,
    dataLabel: input.synthetic ? 'SYNTHETIC_NOT_INVESTMENT_RESEARCH' : 'RESEARCH_INPUTS_NOT_INDEPENDENTLY_VERIFIED',
    status,
    score: rounded(score),
    coveragePct: rounded(coverage),
    evidenceStrengthPct: rounded(evidenceStrength),
    portfolioStatus: 'NOT_ASSESSED',
    reasons,
    pillars: Object.fromEntries(Object.entries(pillars).map(([name, value]) => [name, rounded(value)])),
    metrics: metrics.map(metric => ({ ...metric, points: rounded(metric.points) })),
    gates,
    valuation,
    caveat: 'Uncalibrated research screen, not a buy signal, return probability, maximum-loss estimate, or ' +
      'personalized advice. Evidence metadata is not proof of document contents. Portfolio suitability must be ' +
      'assessed separately.',
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    requireCondition(process.argv.length === 3, 'Usage: node score.mjs <input.json>');
    console.log(JSON.stringify(scoreCompany(JSON.parse(readFileSync(process.argv[2], 'utf8'))), null, 2));
  } catch (error) {
    console.error(`Scoring failed: ${error.message}`);
    process.exitCode = 1;
  }
}
