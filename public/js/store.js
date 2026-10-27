/**
 * Client-Side Schema-Versioned Store for Jashn.
 * The FastAPI backend is completely stateless; all active plan data,
 * completed tasks, and user edits persist safely in localStorage.
 */

const STORAGE_KEY = 'jashn_plan_v1';
const SCHEMA_VERSION = 'v1';

export function validatePlanSchema(data) {
  if (!data || typeof data !== 'object') return false;
  if (!data.plan_id || typeof data.plan_id !== 'string') return false;
  if (data.schema_version !== SCHEMA_VERSION) return false;
  if (!data.brief || typeof data.brief !== 'object') return false;
  if (!data.budget || !Array.isArray(data.budget.categories)) return false;
  if (!data.timeline || !Array.isArray(data.timeline.tasks)) return false;
  if (!Array.isArray(data.vendors)) return false;
  if (!data.ideas || !Array.isArray(data.ideas.themes)) return false;
  return true;
}

export function savePlan(plan) {
  if (!plan) return;
  plan.schema_version = SCHEMA_VERSION;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(plan));
    dispatchStoreUpdate(plan);
  } catch (err) {
    console.error('Failed to save plan to localStorage:', err);
  }
}

export function loadPlan() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (validatePlanSchema(parsed)) {
      return parsed;
    }
    console.warn('Stored plan failed schema validation or has mismatched version; clearing.');
    clearPlan();
    return null;
  } catch (err) {
    console.error('Error loading plan from localStorage:', err);
    return null;
  }
}

export function clearPlan() {
  localStorage.removeItem(STORAGE_KEY);
  dispatchStoreUpdate(null);
}

export function exportPlanJSON(plan) {
  const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(plan, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute('href', dataStr);
  const title = (plan.brief && plan.brief.event_type) ? plan.brief.event_type : 'event';
  downloadAnchor.setAttribute('download', `jashn_${title}_plan.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
}

export function importPlanJSON(jsonString) {
  try {
    const parsed = JSON.parse(jsonString);
    if (validatePlanSchema(parsed)) {
      savePlan(parsed);
      return { success: true, plan: parsed };
    }
    return { success: false, error: 'Invalid Jashn plan JSON or schema version mismatch.' };
  } catch (err) {
    return { success: false, error: 'Failed to parse JSON file: ' + err.message };
  }
}

const listeners = [];
export function onStoreChange(callback) {
  listeners.push(callback);
}

function dispatchStoreUpdate(plan) {
  listeners.forEach(fn => {
    try {
      fn(plan);
    } catch (e) {
      console.error('Store listener error:', e);
    }
  });
}
