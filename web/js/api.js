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

export async function fetchHealth() {
  return await request('/api/health', { method: 'GET' });
}

export async function postIntake(intakeData) {
  return await request('/api/intake', {
    method: 'POST',
    body: JSON.stringify(intakeData)
  });
}

export async function postPlan(brief) {
  return await request('/api/plan', {
    method: 'POST',
    body: JSON.stringify(brief)
  });
}

export async function postReplan(replanData) {
  return await request('/api/replan', {
    method: 'POST',
    body: JSON.stringify(replanData)
  });
}

export async function postRefineIdeas(refineData) {
  return await request('/api/ideas/refine', {
    method: 'POST',
    body: JSON.stringify(refineData)
  });
}
