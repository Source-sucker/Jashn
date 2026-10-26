import { announce, trapFocus } from './a11y.js';
import { fetchHealth } from './api.js';
import { clearPlan, exportPlanJSON, importPlanJSON, loadPlan, savePlan } from './store.js';
import { renderBudgetView } from './views/budgetView.js';
import { renderIdeasView } from './views/ideasView.js';
import { initIntakeView } from './views/intakeView.js';
import { renderOverviewView } from './views/overviewView.js';
import { initReplanModal } from './views/replanModal.js';
import { renderTimelineView } from './views/timelineView.js';
import { renderVendorsView } from './views/vendorsView.js';

let activePlan = null;
let currentTab = 'overview';

document.addEventListener('DOMContentLoaded', async () => {
  // Elements
  const intakeSection = document.getElementById('intake-section');
  const dashboardSection = document.getElementById('dashboard-section');
  const headerActions = document.getElementById('header-plan-actions');
  const aiBanner = document.getElementById('ai-status-banner');
  const aiStatusText = document.getElementById('ai-status-text');
  const btnExport = document.getElementById('btn-export-plan');
  const btnReset = document.getElementById('btn-reset-plan');

  // Check backend health & AI availability
  try {
    const health = await fetchHealth();
    if (!health.ai_available) {
      aiBanner.classList.add('fallback-mode');
      aiStatusText.textContent = '⚡ Rule-based planning active (Gemini API key unconfigured)';
    } else {
      aiBanner.classList.remove('fallback-mode');
      aiStatusText.textContent = `✨ Gemini GenAI Active (${health.model})`;
    }
    aiBanner.classList.remove('hidden');
  } catch (err) {
    console.warn('Backend health check warning:', err);
  }

  // Initialize Intake Controller
  initIntakeView((newPlan) => {
    activePlan = newPlan;
    showDashboard();
  });

  // Initialize Replan Modal Controller
  initReplanModal(
    () => activePlan,
    (updatedPlan) => {
      activePlan = updatedPlan;
      renderCurrentTab();
    }
  );

  // Export Plan Handler
  btnExport.addEventListener('click', () => {
    if (activePlan) {
      exportPlanJSON(activePlan);
      announce('Celebration plan exported as JSON.');
    }
  });

  // Reset / Start Over Handler
  btnReset.addEventListener('click', () => {
    if (confirm('Start over? This will clear your current celebration plan from this browser.')) {
      clearPlan();
      activePlan = null;
      showIntake();
      announce('Cleared plan. Ready for a new celebration.');
    }
  });

  // Tab Navigation Handling
  const tabs = document.querySelectorAll('.dashboard-tabs .tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const tabName = tab.id.replace('tab-', '');
      switchTab(tabName);
    });

    // Keyboard navigation across tabs
    tab.addEventListener('keydown', (e) => {
      const tabList = Array.from(tabs);
      const idx = tabList.indexOf(tab);
      let targetTab = null;

      if (e.key === 'ArrowRight') {
        targetTab = tabList[(idx + 1) % tabList.length];
      } else if (e.key === 'ArrowLeft') {
        targetTab = tabList[(idx - 1 + tabList.length) % tabList.length];
      } else if (e.key === 'Home') {
        targetTab = tabList[0];
      } else if (e.key === 'End') {
        targetTab = tabList[tabList.length - 1];
      }

      if (targetTab) {
        targetTab.focus();
        targetTab.click();
        e.preventDefault();
      }
    });
  });

  function switchTab(tabName) {
    currentTab = tabName;
    tabs.forEach(t => {
      const isSelected = t.id === `tab-${tabName}`;
      t.classList.toggle('active', isSelected);
      t.setAttribute('aria-selected', isSelected);
      t.setAttribute('tabindex', isSelected ? '0' : '-1');
    });

    const panels = document.querySelectorAll('.dashboard-content .tab-panel');
    panels.forEach(p => {
      p.classList.toggle('hidden', p.id !== `view-${tabName}`);
      p.classList.toggle('active', p.id === `view-${tabName}`);
    });

    renderCurrentTab();
    announce(`Switched to ${tabName} view.`);
  }

  function renderCurrentTab() {
    if (!activePlan) return;

    if (activePlan.ai_status_message) {
      aiStatusText.textContent = activePlan.ai_status_message;
      if (!activePlan.is_ai_generated) {
        aiBanner.classList.add('fallback-mode');
      } else {
        aiBanner.classList.remove('fallback-mode');
      }
    }

    const panel = document.getElementById(`view-${currentTab}`);
    if (!panel) return;

    if (currentTab === 'overview') {
      renderOverviewView(panel, activePlan, switchTab);
    } else if (currentTab === 'budget') {
      renderBudgetView(panel, activePlan);
    } else if (currentTab === 'timeline') {
      renderTimelineView(panel, activePlan);
    } else if (currentTab === 'vendors') {
      renderVendorsView(panel, activePlan);
    } else if (currentTab === 'ideas') {
      renderIdeasView(panel, activePlan);
    }
  }

  function showDashboard() {
    intakeSection.classList.add('hidden');
    dashboardSection.classList.remove('hidden');
    headerActions.classList.remove('hidden');
    switchTab('overview');
  }

  function showIntake() {
    dashboardSection.classList.add('hidden');
    headerActions.classList.add('hidden');
    intakeSection.classList.remove('hidden');
  }

  // Check for existing plan in localStorage
  const existingPlan = loadPlan();
  if (existingPlan) {
    activePlan = existingPlan;
    showDashboard();
    announce('Loaded your saved celebration plan from browser storage.');
  } else {
    showIntake();
  }
});
