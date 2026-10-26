import { announce, formatINR, trapFocus } from '../a11y.js';
import { postReplan } from '../api.js';
import { savePlan } from '../store.js';

export function initReplanModal(getCurrentPlan, onPlanUpdated) {
  const modal = document.getElementById('replan-modal');
  const btnOpen = document.getElementById('btn-replan');
  const btnClose = document.getElementById('btn-close-replan-modal');
  const form = document.getElementById('replan-form');
  const budgetInput = document.getElementById('replan-budget');
  const guestsInput = document.getElementById('replan-guests');
  const dateInput = document.getElementById('replan-date');
  const diffContainer = document.getElementById('replan-diff-container');
  const diffList = document.getElementById('replan-diff-list');
  const tradeoffsList = document.getElementById('tradeoff-cards-list');
  const btnExtreme = document.getElementById('btn-test-extreme-replan');

  let releaseFocusTrap = null;
  let latestReplanResult = null;

  btnOpen.addEventListener('click', () => {
    const plan = getCurrentPlan();
    if (!plan) return;

    budgetInput.value = plan.brief.total_budget;
    guestsInput.value = plan.brief.guest_count;
    dateInput.value = plan.brief.event_date;
    diffContainer.classList.add('hidden');
    latestReplanResult = null;

    modal.showModal();
    releaseFocusTrap = trapFocus(modal);
    announce('Opened replanning dialog.');
  });

  btnClose.addEventListener('click', () => {
    if (releaseFocusTrap) releaseFocusTrap();
    modal.close();
  });

  // Extreme replan quick button: budget -50% and moved 2 weeks earlier
  btnExtreme.addEventListener('click', () => {
    const plan = getCurrentPlan();
    if (!plan) return;

    const cutBudget = Math.round(plan.brief.total_budget / 2);
    budgetInput.value = cutBudget;

    const d = new Date(plan.brief.event_date);
    d.setDate(d.getDate() - 14);
    dateInput.value = d.toISOString().split('T')[0];

    announce('Applied extreme test inputs: budget cut by 50% and event date moved 14 days earlier.');
    form.dispatchEvent(new Event('submit'));
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const plan = getCurrentPlan();
    if (!plan) return;

    const newBudget = parseInt(budgetInput.value, 10);
    const newGuests = parseInt(guestsInput.value, 10);
    const newDate = dateInput.value;

    const completedIds = plan.timeline.tasks
      .filter(t => t.is_completed)
      .map(t => t.id);

    // Collect locked categories
    const lockedCats = {};
    plan.budget.categories.forEach(c => {
      if (c.is_locked && c.category_id !== 'contingency') {
        lockedCats[c.category_id] = c.allocated_amount;
      }
    });

    const submitBtn = form.querySelector('#btn-submit-replan');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Calculating...';
    announce('Calculating new budget allocation and trade-off options...');

    try {
      const res = await postReplan({
        current_plan: plan,
        updated_budget: newBudget,
        updated_guest_count: newGuests,
        updated_date: newDate,
        completed_task_ids: completedIds,
        locked_categories: lockedCats
      });

      latestReplanResult = res;
      renderDiffAndTradeoffs(res);
      announce('Replan calculated. Review what changed and pick a trade-off option.');
    } catch (err) {
      announce(`Replan failed: ${err.message}`, 'assertive');
      alert(`Could not recalculate plan: ${err.message}`);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Calculate What Changes';
    }
  });

  function renderDiffAndTradeoffs(replanData) {
    diffList.textContent = '';
    replanData.diff_summary.forEach(d => {
      const li = document.createElement('li');
      li.textContent = d;
      diffList.appendChild(li);
    });

    tradeoffsList.textContent = '';
    replanData.tradeoff_options.forEach(opt => {
      const card = document.createElement('div');
      card.className = 'tradeoff-card';

      const tTitle = document.createElement('h4');
      tTitle.style.color = 'var(--indigo-900)';
      tTitle.style.fontSize = '1.05rem';
      tTitle.style.marginBottom = '0.25rem';
      tTitle.textContent = opt.title;

      const savingP = document.createElement('div');
      savingP.className = 'tradeoff-saving';
      savingP.textContent = `Calculated Saving: ${formatINR(opt.numeric_saving)}`;

      const descP = document.createElement('p');
      descP.style.fontSize = '0.85rem';
      descP.style.margin = '0.5rem 0';
      descP.style.color = 'var(--text-secondary)';
      descP.textContent = opt.description;

      const prosList = document.createElement('ul');
      prosList.style.fontSize = '0.8rem';
      prosList.style.paddingLeft = '1.25rem';
      prosList.style.color = 'var(--emerald-600)';
      opt.pros.forEach(p => {
        const li = document.createElement('li');
        li.textContent = `✓ ${p}`;
        prosList.appendChild(li);
      });

      const btnApply = document.createElement('button');
      btnApply.type = 'button';
      btnApply.className = 'btn btn-primary';
      btnApply.style.marginTop = '0.75rem';
      btnApply.style.fontSize = '0.85rem';
      btnApply.textContent = 'Apply This Trade-Off & Save Plan';
      btnApply.addEventListener('click', () => {
        applyTradeoff(opt, replanData.updated_plan);
      });

      card.appendChild(tTitle);
      card.appendChild(savingP);
      card.appendChild(descP);
      card.appendChild(prosList);
      card.appendChild(btnApply);
      tradeoffsList.appendChild(card);
    });

    diffContainer.classList.remove('hidden');
    diffContainer.scrollIntoView({ behavior: 'smooth' });
  }

  function applyTradeoff(option, plan) {
    // If trade-off modifies guest count or budget, apply and save
    if (option.applied_changes && option.applied_changes.guest_count) {
      plan.brief.guest_count = option.applied_changes.guest_count;
    }
    savePlan(plan);
    announce(`Applied trade-off: ${option.title}. Your dashboard has been updated.`);
    if (releaseFocusTrap) releaseFocusTrap();
    modal.close();
    if (onPlanUpdated) onPlanUpdated(plan);
  }
}
