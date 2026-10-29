/**
 * Client-Side Schema-Versioned Store for Jashn.
 * The FastAPI backend is completely stateless; all active plan data,
 * completed tasks, and user edits persist safely in localStorage.
 */

const STORAGE_KEY = 'jashn_plan_v1';
const SCHEMA_VERSION = 'v1';

/**
 * Validates that an object conforms to the Jashn plan v1 schema specification.
 * @param {any} data - The raw object to validate.
 * @returns {boolean} True if data matches the v1 plan schema, false otherwise.
 */
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

/**
 * Saves a celebration plan to localStorage and notifies active listeners.
 * @param {object} plan - The complete celebration plan object.
 */
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

/**
 * Loads and validates the current celebration plan from localStorage.
 * @returns {object|null} The parsed plan if valid, or null if empty/invalid.
 */
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

/**
 * Clears the active celebration plan from localStorage and notifies listeners.
 */
export function clearPlan() {
  localStorage.removeItem(STORAGE_KEY);
  dispatchStoreUpdate(null);
}

/**
 * Serializes and triggers a client-side browser download of the plan as JSON.
 * @param {object} plan - The celebration plan to export.
 */
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

/**
 * Parses and validates an imported plan JSON string, persisting it if valid.
 * @param {string} jsonString - The raw JSON string from a user-uploaded file.
 * @returns {{success: boolean, plan?: object, error?: string}} Import result object.
 */
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
/**
 * Registers a callback invoked whenever the persisted plan is saved or cleared.
 * @param {Function} callback - Listener receiving the updated plan (or null).
 */
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
