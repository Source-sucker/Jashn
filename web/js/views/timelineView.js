import { announce } from '../a11y.js';
import { savePlan } from '../store.js';

export function renderTimelineView(container, plan) {
  container.textContent = '';

  const { timeline } = plan;

  // Header & Info
  const header = document.createElement('div');
  header.className = 'budget-overview-header';

  const hLeft = document.createElement('div');
  const title = document.createElement('h2');
  title.className = 'section-title';
  title.textContent = 'Celebration Timeline & Checklist';

  const sub = document.createElement('p');
  sub.className = 'section-subtitle';
  sub.textContent = 'Tasks are scheduled backwards from your event date. Compressed timelines are flagged as Rush; overdue tasks are marked Urgent.';
  hLeft.appendChild(title);
  hLeft.appendChild(sub);

  const hRight = document.createElement('div');
  hRight.style.textAlign = 'right';
  const cLabel = document.createElement('div');
  cLabel.style.fontSize = '0.85rem';
  cLabel.style.color = 'var(--text-secondary)';
  cLabel.textContent = 'Days Remaining:';
  const cVal = document.createElement('div');
  cVal.style.fontSize = '1.8rem';
  cVal.style.fontWeight = '800';
  cVal.style.color = timeline.is_compressed ? 'var(--marigold-600)' : 'var(--indigo-900)';
  cVal.textContent = `${timeline.days_remaining} Days`;
  if (timeline.is_compressed) {
    const rushBadge = document.createElement('span');
    rushBadge.className = 'badge badge-marigold';
    rushBadge.textContent = '⚡ Rush Compressed';
    hRight.appendChild(rushBadge);
  }
  hRight.appendChild(cLabel);
  hRight.appendChild(cVal);

  header.appendChild(hLeft);
  header.appendChild(hRight);
  container.appendChild(header);

  // Filter Buttons
  const filterRow = document.createElement('div');
  filterRow.className = 'timeline-filters';
  filterRow.setAttribute('role', 'group');
  filterRow.setAttribute('aria-label', 'Filter tasks');

  const filters = [
    { id: 'all', label: 'All Tasks' },
    { id: 'urgent_rush', label: 'Urgent & Rush' },
    { id: 'incomplete', label: 'Incomplete' },
    { id: 'completed', label: 'Completed' }
  ];

  let activeFilter = 'all';

  filters.forEach(f => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `btn btn-ghost ${f.id === 'all' ? 'active' : ''}`;
    btn.style.color = 'var(--indigo-900)';
    btn.style.borderColor = 'var(--border-strong)';
    btn.textContent = f.label;
    btn.addEventListener('click', () => {
      activeFilter = f.id;
      filterRow.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderPhaseTaskList();
    });
    filterRow.appendChild(btn);
  });
  container.appendChild(filterRow);

  const phasesContainer = document.createElement('div');
  phasesContainer.id = 'phases-container';
  container.appendChild(phasesContainer);

  function renderPhaseTaskList() {
    phasesContainer.textContent = '';

    // Group tasks by phase
    const phases = timeline.phases || [
      'Foundations & Venue',
      'Key Vendors',
      'Details & Decor',
      'Final Week Prep',
      'Event Day Execution'
    ];

    phases.forEach(phaseName => {
      let phaseTasks = timeline.tasks.filter(t => t.phase === phaseName);

      if (activeFilter === 'urgent_rush') {
        phaseTasks = phaseTasks.filter(t => t.is_urgent || t.is_rush);
      } else if (activeFilter === 'incomplete') {
        phaseTasks = phaseTasks.filter(t => !t.is_completed);
      } else if (activeFilter === 'completed') {
        phaseTasks = phaseTasks.filter(t => t.is_completed);
      }

      if (phaseTasks.length === 0) return;

      const phaseSection = document.createElement('section');
      phaseSection.className = 'timeline-phase';

      const phaseTitle = document.createElement('h3');
      phaseTitle.className = 'phase-title';
      phaseTitle.textContent = `${phaseName} (${phaseTasks.filter(t => t.is_completed).length}/${phaseTasks.length} done)`;
      phaseSection.appendChild(phaseTitle);

      const ul = document.createElement('ul');
      ul.className = 'task-list';

      phaseTasks.forEach(task => {
        const li = document.createElement('li');
        li.className = 'task-item';
        if (task.is_completed) li.classList.add('completed');
        if (task.is_urgent) li.classList.add('urgent');
        else if (task.is_rush) li.classList.add('rush');

        const left = document.createElement('div');
        left.className = 'task-left';

        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'task-checkbox';
        cb.checked = task.is_completed;
        cb.setAttribute('aria-label', `Mark complete: ${task.title}`);
        cb.addEventListener('change', () => {
          task.is_completed = cb.checked;
          savePlan(plan);
          announce(`${task.title} marked ${task.is_completed ? 'completed' : 'incomplete'}`);
          renderPhaseTaskList();
        });

        const titleText = document.createElement('span');
        titleText.className = 'task-title';
        titleText.textContent = task.title;

        left.appendChild(cb);
        left.appendChild(titleText);

        const right = document.createElement('div');
        right.className = 'task-meta';

        if (task.is_urgent) {
          const uBadge = document.createElement('span');
          uBadge.className = 'badge badge-unrealistic';
          uBadge.textContent = 'Urgent';
          right.appendChild(uBadge);
        } else if (task.is_rush) {
          const rBadge = document.createElement('span');
          rBadge.className = 'badge badge-tight';
          rBadge.textContent = 'Rush';
          right.appendChild(rBadge);
        }

        if (task.is_blocked) {
          const bBadge = document.createElement('span');
          bBadge.className = 'badge';
          bBadge.style.background = '#e5e7eb';
          bBadge.style.color = '#374151';
          bBadge.textContent = 'Blocked by pre-requisite';
          right.appendChild(bBadge);
        }

        const dueDateSpan = document.createElement('span');
        dueDateSpan.style.fontSize = '0.85rem';
        dueDateSpan.style.fontWeight = '600';
        dueDateSpan.style.color = 'var(--text-secondary)';
        dueDateSpan.textContent = `Due ${task.due_date}`;
        right.appendChild(dueDateSpan);

        li.appendChild(left);
        li.appendChild(right);
        ul.appendChild(li);
      });

      phaseSection.appendChild(ul);
      phasesContainer.appendChild(phaseSection);
    });

    if (phasesContainer.children.length === 0) {
      const emptyP = document.createElement('p');
      emptyP.style.color = 'var(--text-muted)';
      emptyP.textContent = 'No tasks match the selected filter.';
      phasesContainer.appendChild(emptyP);
    }
  }

  renderPhaseTaskList();
}
