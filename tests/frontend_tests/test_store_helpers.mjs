import test from 'node:test';
import assert from 'node:assert/strict';

// Pure helper: formatCurrencyINR
export function formatCurrencyINR(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) return '₹0';
  const num = Math.round(Number(amount));
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(num);
}

// Pure helper: validatePlanSchema
export function validatePlanSchema(data) {
  if (!data || typeof data !== 'object') return false;
  if (!data.plan_id || typeof data.plan_id !== 'string') return false;
  if (data.schema_version !== 'v1') return false;
  if (!data.brief || typeof data.brief !== 'object') return false;
  if (!data.budget || !Array.isArray(data.budget.categories)) return false;
  if (!data.timeline || !Array.isArray(data.timeline.tasks)) return false;
  if (!Array.isArray(data.vendors)) return false;
  if (!data.ideas || !Array.isArray(data.ideas.themes)) return false;
  return true;
}

test('formatCurrencyINR formats numbers using Indian digit grouping (en-IN)', () => {
  assert.equal(formatCurrencyINR(0), '₹0');
  assert.equal(formatCurrencyINR(1000), '₹1,000');
  assert.equal(formatCurrencyINR(20000), '₹20,000');
  assert.equal(formatCurrencyINR(800000), '₹8,00,000');
  assert.equal(formatCurrencyINR(2500000), '₹25,00,000');
  assert.equal(formatCurrencyINR(10000000), '₹1,00,00,000');
});

test('validatePlanSchema correctly validates v1 plan structures', () => {
  const validPlan = {
    plan_id: 'plan_test123',
    schema_version: 'v1',
    created_at: '2026-10-26T12:00:00Z',
    brief: { event_type: 'wedding', guest_count: 200, total_budget: 800000 },
    budget: { total_budget: 800000, categories: [] },
    timeline: { tasks: [] },
    vendors: [],
    ideas: { themes: [] }
  };
  assert.equal(validatePlanSchema(validPlan), true);

  // Invalid: missing plan_id
  assert.equal(validatePlanSchema({ schema_version: 'v1' }), false);

  // Invalid: older schema version
  assert.equal(validatePlanSchema({ ...validPlan, schema_version: 'v0' }), false);

  // Invalid: null / empty object
  assert.equal(validatePlanSchema(null), false);
  assert.equal(validatePlanSchema({}), false);
});

test('extractDetailsFromText accurately parses Indian natural language celebration descriptions', async () => {
  const { extractDetailsFromText } = await import('../../web/js/views/intakeView.js');
  const text = "Sister's wedding in Lucknow for 300 guests with 12 Lakh budget in February";
  const parsed = extractDetailsFromText(text);
  assert.equal(parsed.event_type, 'wedding');
  assert.equal(parsed.guest_count, 300);
  assert.equal(parsed.total_budget, 1200000);
  assert.equal(parsed.city, 'Lucknow');
  assert.ok(parsed.event_date);

  const bdayText = "Daughter's 5th birthday party in Bengaluru with 35 kids and 45000 budget";
  const bdayParsed = extractDetailsFromText(bdayText);
  assert.equal(bdayParsed.event_type, 'birthday');
  assert.equal(bdayParsed.city, 'Bengaluru');
  assert.equal(bdayParsed.total_budget, 45000);
});

