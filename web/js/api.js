/**
 * HTTP API client for Jashn endpoints.
 */

const API_TIMEOUT_MS = 20000;

async function request(endpoint, options = {}) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    const res = await fetch(endpoint, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      }
    });

    clearTimeout(id);

    if (!res.ok) {
      let errorMsg = `Server error (${res.status})`;
      try {
        const errorData = await res.json();
        if (errorData && errorData.detail) {
          errorMsg = errorData.detail;
        }
      } catch (_) {}
      throw new Error(errorMsg);
    }

    return await res.json();
  } catch (err) {
    clearTimeout(id);
    if (err.name === 'AbortError') {
      throw new Error('Request timed out. The server took too long to respond. Please retry.');
    }
    throw err;
  }
}

/**
 * Checks system health and backend service connectivity.
 * @returns {Promise<object>} Health status object with timestamp and version.
 */
export async function fetchHealth() {
  return await request('/api/health', { method: 'GET' });
}

/**
 * Submits raw intake data to extract structured details or clarifying questions.
 * @param {object} intakeData - Intake request payload.
 * @returns {Promise<object>} IntakeResponse with parsed brief or clarifying questions.
 */
export async function postIntake(intakeData) {
  return await request('/api/intake', {
    method: 'POST',
    body: JSON.stringify(intakeData)
  });
}

/**
 * Generates an end-to-end celebration plan for a structured event brief.
 * @param {object} brief - Validated event brief payload.
 * @param {boolean} [enrich=true] - Whether to invoke AI theme enrichment.
 * @returns {Promise<object>} Full PlanResponse object.
 */
export async function postPlan(brief, enrich = true) {
  const url = enrich ? '/api/plan' : '/api/plan?enrich=false';
  return await request(url, {
    method: 'POST',
    body: JSON.stringify(brief)
  });
}

/**
 * Progressively enriches an existing plan's creative ideas and vendor questions.
 * @param {object} enrichData - Brief, category summary, and days remaining.
 * @returns {Promise<object>} Enriched ideas report with vendor custom questions.
 */
export async function postPlanEnrich(enrichData) {
  return await request('/api/plan/enrich', {
    method: 'POST',
    body: JSON.stringify(enrichData)
  });
}

/**
 * Recomputes budget allocations, timeline offsets, and trade-offs after parameter changes.
 * @param {object} replanData - Current plan and changed fields (budget, guests, date, priorities, locks).
 * @returns {Promise<object>} ReplanResponse with updated plan, trade-offs, and explanation.
 */
export async function postReplan(replanData) {
  return await request('/api/replan', {
    method: 'POST',
    body: JSON.stringify(replanData)
  });
}

/**
 * Refines creative themes interactively using natural language instructions.
 * @param {object} refineData - Current themes, event brief, and user refinement prompt.
 * @returns {Promise<object>} Updated IdeasReport with refined themes and alignment note.
 */
export async function postRefineIdeas(refineData) {
  return await request('/api/ideas/refine', {
    method: 'POST',
    body: JSON.stringify(refineData)
  });
}
