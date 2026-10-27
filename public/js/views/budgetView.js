import { announce, formatINR } from '../a11y.js';
import { savePlan } from '../store.js';

const PALETTE = [
  '#4338ca', '#d97706', '#059669', '#6366f1',
  '#f59e0b', '#ec4899', '#14b8a6', '#8b5cf6', '#64748b'
];

export function renderBudgetView(container, plan) {
  container.textContent = '';

  const { budget } = plan;
  const totalActual = budget.categories.reduce((acc, c) => acc + (c.actual_spent || 0), 0);
  const isOverBudget = totalActual > budget.total_budget;

  // Header & Summary
  const header = document.createElement('div');
  header.className = 'budget-overview-header';

  const hLeft = document.createElement('div');
  const title = document.createElement('h2');
  title.className = 'section-title';
  title.textContent = 'Budget Allocation & Spending Tracker';

  const sub = document.createElement('p');
  sub.className = 'section-subtitle';
  sub.textContent = 'All allocations are code-calculated estimates. Enter actual vendor payments to track your real expenses against the ceiling.';
  hLeft.appendChild(title);
  hLeft.appendChild(sub);

  const hRight = document.createElement('div');
  hRight.style.textAlign = 'right';
  const totalLabel = document.createElement('div');
  totalLabel.style.fontSize = '0.85rem';
  totalLabel.style.color = 'var(--text-secondary)';
  totalLabel.textContent = 'Total Budget Ceiling:';
  const totalVal = document.createElement('div');
  totalVal.style.fontSize = '1.8rem';
  totalVal.style.fontWeight = '800';
  totalVal.style.color = 'var(--indigo-900)';
  totalVal.textContent = formatINR(budget.total_budget);
  hRight.appendChild(totalLabel);
  hRight.appendChild(totalVal);

  header.appendChild(hLeft);
  header.appendChild(hRight);
  container.appendChild(header);

  // Over-budget alert if applicable
  if (isOverBudget) {
    const alertBox = document.createElement('div');
    alertBox.className = 'error-summary';
    alertBox.textContent = `⚠️ Over Budget Warning: Total actual spent (${formatINR(totalActual)}) exceeds your total planned ceiling (${formatINR(budget.total_budget)}) by ${formatINR(totalActual - budget.total_budget)}. Consider using 'Replan & Adapt' to adjust categories.`;
    container.appendChild(alertBox);
  }

  // Layout: Donut Chart + Legend Cards
  const donutCard = document.createElement('div');
  donutCard.className = 'card';
  donutCard.style.marginBottom = '2rem';

  const donutLayout = document.createElement('div');
  donutLayout.className = 'donut-layout';

  // SVG Donut
  const svgWrapper = document.createElement('div');
  svgWrapper.className = 'donut-svg-container';
  svgWrapper.innerHTML = createDonutSVG(budget.categories, budget.total_budget);
  donutLayout.appendChild(svgWrapper);

  // Legend Summary
  const legendBox = document.createElement('div');
  const legTitle = document.createElement('h3');
  legTitle.style.marginBottom = '0.75rem';
  legTitle.style.color = 'var(--indigo-900)';
  legTitle.textContent = 'Category Share Breakdown';
  legendBox.appendChild(legTitle);

  const legendList = document.createElement('div');
  legendList.style.display = 'grid';
  legendList.style.gridTemplateColumns = 'repeat(auto-fit, minmax(200px, 1fr))';
  legendList.style.gap = '0.5rem';

  budget.categories.forEach((cat, idx) => {
    const item = document.createElement('div');
    item.style.display = 'flex';
    item.style.alignItems = 'center';
    item.style.gap = '0.5rem';
    item.style.fontSize = '0.85rem';

    const dot = document.createElement('span');
    dot.style.width = '12px';
    dot.style.height = '12px';
    dot.style.borderRadius = '50%';
    dot.style.backgroundColor = PALETTE[idx % PALETTE.length];
    dot.style.flexShrink = '0';

    const text = document.createElement('span');
    text.textContent = `${cat.label}: ${cat.percentage}% (${formatINR(cat.allocated_amount)})`;

    item.appendChild(dot);
    item.appendChild(text);
    legendList.appendChild(item);
  });
  legendBox.appendChild(legendList);
  donutLayout.appendChild(legendBox);

  donutCard.appendChild(donutLayout);
  container.appendChild(donutCard);

  // Detailed Data Table
  const tableCard = document.createElement('div');
  tableCard.className = 'card';

  const tableTitle = document.createElement('h3');
  tableTitle.className = 'card-title';
  tableTitle.textContent = '📊 Category Detail & Actuals Log';
  tableCard.appendChild(tableTitle);

  const tableWrapper = document.createElement('div');
  tableWrapper.className = 'data-table-container';

  const table = document.createElement('table');
  table.className = 'data-table';
  table.setAttribute('aria-label', 'Detailed budget breakdown table');

  table.innerHTML = `
    <thead>
      <tr>
        <th scope="col">Category</th>
        <th scope="col" class="num-col">Share</th>
        <th scope="col" class="num-col">Planned Estimate (INR)</th>
        <th scope="col" class="num-col">Actual Spent (INR)</th>
        <th scope="col" class="num-col">Variance</th>
        <th scope="col">Notes</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector('tbody');

  budget.categories.forEach(cat => {
    const tr = document.createElement('tr');

    const tdName = document.createElement('td');
    tdName.style.fontWeight = '600';
    tdName.textContent = cat.label;
    if (cat.is_locked) {
      const lockBadge = document.createElement('span');
      lockBadge.style.fontSize = '0.75rem';
      lockBadge.style.marginLeft = '0.4rem';
      lockBadge.textContent = '🔒 Locked';
      tdName.appendChild(lockBadge);
    }

    const tdPct = document.createElement('td');
    tdPct.className = 'num-col';
    tdPct.textContent = `${cat.percentage}%`;

    const tdAlloc = document.createElement('td');
    tdAlloc.className = 'num-col';
    tdAlloc.textContent = formatINR(cat.allocated_amount);

    const tdActual = document.createElement('td');
    tdActual.className = 'num-col';
    const inputActual = document.createElement('input');
    inputActual.type = 'number';
    inputActual.className = 'input-actual-spent';
    inputActual.value = cat.actual_spent || 0;
    inputActual.min = '0';
    inputActual.step = '500';
    inputActual.setAttribute('aria-label', `Actual spent on ${cat.label}`);
    inputActual.addEventListener('change', () => {
      cat.actual_spent = Math.max(0, parseInt(inputActual.value, 10) || 0);
      savePlan(plan);
      announce(`Updated actual spent for ${cat.label} to ${formatINR(cat.actual_spent)}`);
      renderBudgetView(container, plan);
    });
    tdActual.appendChild(inputActual);

    const tdVar = document.createElement('td');
    tdVar.className = 'num-col';
    const diff = (cat.actual_spent || 0) - cat.allocated_amount;
    if (diff > 0) {
      tdVar.style.color = 'var(--rose-600)';
      tdVar.textContent = `+${formatINR(diff)} (Over)`;
    } else if (diff < 0) {
      tdVar.style.color = 'var(--emerald-600)';
      tdVar.textContent = `${formatINR(diff)} (Under)`;
    } else {
      tdVar.textContent = '₹0';
    }

    const tdNotes = document.createElement('td');
    tdNotes.style.fontSize = '0.85rem';
    tdNotes.style.color = 'var(--text-muted)';
    tdNotes.textContent = cat.notes || '';

    tr.appendChild(tdName);
    tr.appendChild(tdPct);
    tr.appendChild(tdAlloc);
    tr.appendChild(tdActual);
    tr.appendChild(tdVar);
    tr.appendChild(tdNotes);
    tbody.appendChild(tr);
  });

  tableWrapper.appendChild(table);
  tableCard.appendChild(tableWrapper);
  container.appendChild(tableCard);
}

function createDonutSVG(categories, totalBudget) {
  const size = 200;
  const strokeWidth = 32;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  let offset = 0;
  const circles = categories.map((cat, idx) => {
    const fraction = totalBudget > 0 ? (cat.allocated_amount / totalBudget) : 0;
    const strokeDasharray = `${fraction * circumference} ${circumference}`;
    const strokeDashoffset = -offset;
    offset += fraction * circumference;
    const color = PALETTE[idx % PALETTE.length];

    return `
      <circle 
        cx="${size / 2}" 
        cy="${size / 2}" 
        r="${radius}" 
        fill="transparent" 
        stroke="${color}" 
        stroke-width="${strokeWidth}" 
        stroke-dasharray="${strokeDasharray}" 
        stroke-dashoffset="${strokeDashoffset}"
        role="graphics-symbol"
        aria-label="${cat.label}: ${cat.percentage}%"
      />
    `;
  }).join('');

  return `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="transform: rotate(-90deg);" role="img" aria-label="Budget distribution donut chart">
      ${circles}
    </svg>
  `;
}
