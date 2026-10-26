import { formatINR } from '../a11y.js';
import { savePlan } from '../store.js';

export function renderOverviewView(container, plan, onSwitchTab) {
  container.textContent = '';

  const { brief, budget, timeline } = plan;

  // 1. Hero Countdown Banner
  const hero = document.createElement('div');
  hero.className = 'overview-hero';

  const heroLeft = document.createElement('div');
  const heroTitle = document.createElement('h2');
  heroTitle.className = 'section-title';
  heroTitle.style.color = '#ffffff';
  heroTitle.textContent = `${brief.event_type.toUpperCase()} IN ${brief.city.toUpperCase()}`;

  const heroSub = document.createElement('p');
  heroSub.textContent = `${brief.guest_count} Guests • Budget: ${formatINR(brief.total_budget)} • ${brief.vibe || 'Family Celebration'}`;
  heroSub.style.color = 'var(--indigo-100)';

  heroLeft.appendChild(heroTitle);
  heroLeft.appendChild(heroSub);

  const countdown = document.createElement('div');
  countdown.className = 'countdown-box';
  const cNum = document.createElement('div');
  cNum.className = 'countdown-num';
  cNum.textContent = Math.max(0, timeline.days_remaining);
  const cLabel = document.createElement('div');
  cLabel.className = 'countdown-label';
  cLabel.textContent = 'Days Remaining';
  countdown.appendChild(cNum);
  countdown.appendChild(cLabel);

  hero.appendChild(heroLeft);
  hero.appendChild(countdown);
  container.appendChild(hero);

  // 2. Overview Grid (Feasibility Card, Budget Gauge, Next 3 Tasks)
  const grid = document.createElement('div');
  grid.className = 'overview-grid';

  // Feasibility Card
  const feasCard = document.createElement('div');
  feasCard.className = 'card';
  const feasTitle = document.createElement('h3');
  feasTitle.className = 'card-title';
  feasTitle.textContent = '🎯 Budget Health & Feasibility';

  const badgeSpan = document.createElement('span');
  badgeSpan.className = `badge badge-${budget.feasibility_status}`;
  badgeSpan.textContent = budget.feasibility_status.toUpperCase();

  const feasReason = document.createElement('p');
  feasReason.style.marginTop = '0.75rem';
  feasReason.style.color = 'var(--text-secondary)';
  feasReason.textContent = budget.feasibility_reason;

  const perGuest = document.createElement('p');
  perGuest.style.marginTop = '0.5rem';
  perGuest.style.fontWeight = '700';
  perGuest.textContent = `Per-Guest Spend: ${formatINR(budget.per_guest_spend)} / attendee`;

  feasCard.appendChild(feasTitle);
  feasCard.appendChild(badgeSpan);
  feasCard.appendChild(feasReason);
  feasCard.appendChild(perGuest);
  grid.appendChild(feasCard);

  // Budget Progress Card
  const budgetCard = document.createElement('div');
  budgetCard.className = 'card';
  const bTitle = document.createElement('h3');
  bTitle.className = 'card-title';
  bTitle.textContent = '💰 Planned vs Actual Spending';

  const totalActual = budget.categories.reduce((acc, c) => acc + (c.actual_spent || 0), 0);
  const pctSpent = budget.total_budget > 0 ? Math.min(100, Math.round((totalActual / budget.total_budget) * 100)) : 0;

  const barContainer = document.createElement('div');
  barContainer.className = 'progress-bar-container';
  const barFill = document.createElement('div');
  barFill.className = 'progress-bar-fill';
  barFill.style.width = `${pctSpent}%`;
  barContainer.appendChild(barFill);

  const spendSummary = document.createElement('div');
  spendSummary.style.display = 'flex';
  spendSummary.style.justifyContent = 'space-between';
  spendSummary.style.fontSize = '0.9rem';
  spendSummary.style.marginTop = '0.5rem';

  const spanSpent = document.createElement('span');
  spanSpent.textContent = `Spent: ${formatINR(totalActual)}`;
  const spanTotal = document.createElement('span');
  spanTotal.textContent = `Total Budget: ${formatINR(budget.total_budget)}`;
  spendSummary.appendChild(spanSpent);
  spendSummary.appendChild(spanTotal);

  const btnGoBudget = document.createElement('button');
  btnGoBudget.className = 'btn btn-secondary';
  btnGoBudget.style.marginTop = '1rem';
  btnGoBudget.textContent = 'View Detailed Budget Breakdown →';
  btnGoBudget.addEventListener('click', () => onSwitchTab('budget'));

  budgetCard.appendChild(bTitle);
  budgetCard.appendChild(barContainer);
  budgetCard.appendChild(spendSummary);
  budgetCard.appendChild(btnGoBudget);
  grid.appendChild(budgetCard);

  // Next 3 Tasks Card
  const tasksCard = document.createElement('div');
  tasksCard.className = 'card';
  const tTitle = document.createElement('h3');
  tTitle.className = 'card-title';
  tTitle.textContent = '⚡ Next Up: High Priority Tasks';

  const incompleteTasks = timeline.tasks.filter(t => !t.is_completed);
  const next3 = incompleteTasks.slice(0, 3);

  if (next3.length === 0) {
    const allDone = document.createElement('p');
    allDone.textContent = '🎉 All tasks are marked completed!';
    tasksCard.appendChild(tTitle);
    tasksCard.appendChild(allDone);
  } else {
    const ul = document.createElement('ul');
    ul.className = 'task-list';

    next3.forEach(task => {
      const li = document.createElement('li');
      li.className = 'task-item';
      if (task.is_urgent) li.classList.add('urgent');
      else if (task.is_rush) li.classList.add('rush');

      const left = document.createElement('div');
      left.className = 'task-left';

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'task-checkbox';
      cb.checked = task.is_completed;
      cb.setAttribute('aria-label', `Mark task complete: ${task.title}`);
      cb.addEventListener('change', () => {
        task.is_completed = cb.checked;
        savePlan(plan);
        renderOverviewView(container, plan, onSwitchTab);
      });

      const spanTitle = document.createElement('span');
      spanTitle.className = 'task-title';
      spanTitle.textContent = task.title;

      left.appendChild(cb);
      left.appendChild(spanTitle);

      const right = document.createElement('span');
      right.style.fontSize = '0.8rem';
      right.style.fontWeight = '600';
      right.style.color = task.is_urgent ? 'var(--rose-600)' : 'var(--text-muted)';
      right.textContent = `Due ${task.due_date}`;

      li.appendChild(left);
      li.appendChild(right);
      ul.appendChild(li);
    });

    tasksCard.appendChild(tTitle);
    tasksCard.appendChild(ul);

    const btnGoTimeline = document.createElement('button');
    btnGoTimeline.className = 'btn btn-secondary';
    btnGoTimeline.style.marginTop = '1rem';
    btnGoTimeline.textContent = 'Open Full Timeline →';
    btnGoTimeline.addEventListener('click', () => onSwitchTab('timeline'));
    tasksCard.appendChild(btnGoTimeline);
  }

  grid.appendChild(tasksCard);
  container.appendChild(grid);
}
