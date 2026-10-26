import { announce, formatIndianWords } from '../a11y.js';
import { postIntake, postPlan } from '../api.js';
import { savePlan } from '../store.js';

export function initIntakeView(onPlanGenerated) {
  const form = document.getElementById('intake-form');
  const errorSummary = document.getElementById('form-error-summary');
  const errorList = document.getElementById('error-list');
  const budgetInput = document.getElementById('total-budget');
  const budgetHint = document.getElementById('budget-in-words');
  const clarifyingBox = document.getElementById('clarifying-questions-container');
  const clarifyingList = document.getElementById('clarifying-questions-list');
  const btnSubmit = document.getElementById('btn-create-plan');
  const submitText = btnSubmit.querySelector('.btn-text');
  const submitSpinner = btnSubmit.querySelector('.btn-spinner');

  // Budget in words helper
  budgetInput.addEventListener('input', () => {
    const val = parseFloat(budgetInput.value);
    budgetHint.textContent = formatIndianWords(val);
  });

  // Priority Chips Reordering / Ranking
  const priorityContainer = document.getElementById('priority-chips');
  priorityContainer.addEventListener('click', (e) => {
    const chip = e.target.closest('.priority-chip');
    if (!chip) return;
    // Move clicked chip to first position (top priority)
    priorityContainer.prepend(chip);
    updateChipRanks();
    announce(`Set ${chip.textContent.trim()} as top priority`);
  });

  function updateChipRanks() {
    const chips = priorityContainer.querySelectorAll('.priority-chip');
    chips.forEach((c, idx) => {
      const rankSpan = c.querySelector('.chip-rank');
      if (rankSpan) rankSpan.textContent = idx + 1;
      c.setAttribute('aria-label', `Priority ${idx + 1}: ${c.textContent.replace(/^\d+/, '').trim()}`);
    });
  }

  function getPriorities() {
    const chips = priorityContainer.querySelectorAll('.priority-chip');
    return Array.from(chips).map(c => c.dataset.category);
  }

  // Sample Loaders
  document.getElementById('btn-sample-wedding').addEventListener('click', () => {
    document.querySelector('input[name="event_type"][value="wedding"]').checked = true;
    // Set date to 5 months in the future
    const d = new Date();
    d.setMonth(d.getMonth() + 5);
    document.getElementById('event-date').value = d.toISOString().split('T')[0];
    document.getElementById('guest-count').value = '250';
    document.getElementById('total-budget').value = '800000';
    budgetHint.textContent = formatIndianWords(800000);
    document.getElementById('event-city').value = 'Jaipur';
    document.getElementById('venue-preference').value = 'Heritage Haveli or Lawn';
    document.getElementById('event-vibe').value = 'Royal Rajasthani Heritage';
    document.getElementById('dietary-notes').value = 'North Indian Vegetarian with Jain counters';
    document.getElementById('event-description').value = 'Planning a traditional 2-day family wedding celebration in Jaipur with 250 guests.';
    clearErrors();
    announce('Loaded sample wedding details for ₹8,00,000');
  });

  document.getElementById('btn-sample-birthday').addEventListener('click', () => {
    document.querySelector('input[name="event_type"][value="birthday"]').checked = true;
    const d = new Date();
    d.setDate(d.getDate() + 25);
    document.getElementById('event-date').value = d.toISOString().split('T')[0];
    document.getElementById('guest-count').value = '35';
    document.getElementById('total-budget').value = '45000';
    budgetHint.textContent = formatIndianWords(45000);
    document.getElementById('event-city').value = 'Bengaluru';
    document.getElementById('venue-preference').value = 'Apartment Clubhouse';
    document.getElementById('event-vibe').value = 'Colorful Superhero Carnival';
    document.getElementById('dietary-notes').value = 'Kids snacks, eggless chocolate cake';
    document.getElementById('event-description').value = '5th birthday party for 35 guests with games, magician, and cake cutting.';
    clearErrors();
    announce('Loaded sample birthday details for ₹45,000');
  });

  function clearErrors() {
    errorSummary.classList.add('hidden');
    errorList.textContent = '';
  }

  function showErrors(messages) {
    errorList.textContent = '';
    messages.forEach(msg => {
      const li = document.createElement('li');
      li.textContent = msg;
      errorList.appendChild(li);
    });
    errorSummary.classList.remove('hidden');
    errorSummary.focus();
    announce(`Form error: ${messages.join('. ')}`, 'assertive');
  }

  function setLoading(loading) {
    if (loading) {
      btnSubmit.disabled = true;
      submitSpinner.classList.remove('hidden');
      submitText.textContent = 'Analyzing & Calculating...';
    } else {
      btnSubmit.disabled = false;
      submitSpinner.classList.add('hidden');
      submitText.textContent = 'Build My Celebration Plan';
    }
  }

  // Form Submit Handler
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();

    const errors = [];
    const eventTypeInput = form.querySelector('input[name="event_type"]:checked');
    const eventType = eventTypeInput ? eventTypeInput.value : '';
    const eventDate = document.getElementById('event-date').value;
    const guestCount = parseInt(document.getElementById('guest-count').value, 10);
    const totalBudget = parseInt(document.getElementById('total-budget').value, 10);
    const description = document.getElementById('event-description').value.trim();

    if (!description) {
      if (!eventDate) errors.push('Event date is required.');
      if (isNaN(guestCount) || guestCount < 1) errors.push('Please enter a valid guest count (minimum 1).');
      if (isNaN(totalBudget) || totalBudget < 5000) errors.push('Please enter a budget of at least ₹5,000.');
    }

    if (errors.length > 0) {
      showErrors(errors);
      return;
    }

    setLoading(true);
    announce('Processing celebration details...');

    const payload = {
      description,
      event_type: eventType,
      event_date: eventDate || null,
      city: document.getElementById('event-city').value.trim() || null,
      guest_count: isNaN(guestCount) ? null : guestCount,
      total_budget: isNaN(totalBudget) ? null : totalBudget,
      priorities: getPriorities(),
      venue_preference: document.getElementById('venue-preference').value.trim() || null,
      dietary_cultural_notes: document.getElementById('dietary-notes').value.trim() || null,
      vibe: document.getElementById('event-vibe').value.trim() || null
    };

    const isFullyStructured = Boolean(
      eventType && eventDate && !isNaN(guestCount) && guestCount >= 1 && !isNaN(totalBudget) && totalBudget >= 5000
    );

    try {
      let brief = null;

      if (isFullyStructured) {
        // Form is fully structured: skip AI intake call completely
        brief = {
          event_type: eventType,
          event_date: eventDate,
          city: document.getElementById('event-city').value.trim() || 'Tier 2 City',
          guest_count: guestCount,
          total_budget: totalBudget,
          priorities: getPriorities(),
          venue_preference: document.getElementById('venue-preference').value.trim() || '',
          dietary_cultural_notes: document.getElementById('dietary-notes').value.trim() || '',
          vibe: document.getElementById('event-vibe').value.trim() || '',
          user_description: description
        };
      } else {
        // Use AI intake only for free-text description or when fields are missing
        const intakeRes = await postIntake(payload);

        if (!intakeRes.is_complete) {
          // Show clarifying questions inline
          renderClarifyingQuestions(intakeRes.clarifying_questions);
          setLoading(false);
          return;
        }
        brief = intakeRes.brief;
      }

      // Intake complete: generate plan!
      clarifyingBox.classList.add('hidden');
      announce('Generating tailored budget, timeline, and cultural themes...');
      const planRes = await postPlan(brief);

      savePlan(planRes);
      setLoading(false);
      announce('Plan ready! Showing your celebration dashboard.');
      if (onPlanGenerated) onPlanGenerated(planRes);
    } catch (err) {
      setLoading(false);
      showErrors([err.message || 'Unable to generate plan. Please verify inputs and retry.']);
    }
  });

  function renderClarifyingQuestions(questions) {
    clarifyingList.textContent = '';
    if (!questions || questions.length === 0) return;

    questions.forEach(q => {
      const card = document.createElement('div');
      card.className = 'clarifying-question-card';

      const label = document.createElement('p');
      label.className = 'form-label';
      label.textContent = q.question;
      card.appendChild(label);

      if (q.options && q.options.length > 0) {
        const row = document.createElement('div');
        row.className = 'clarifying-options-row';

        q.options.forEach(opt => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'btn-chip-option';
          btn.textContent = opt;
          btn.addEventListener('click', () => {
            applyClarifyingAnswer(q.field, opt);
          });
          row.appendChild(btn);
        });
        card.appendChild(row);
      }
      clarifyingList.appendChild(card);
    });

    clarifyingBox.classList.remove('hidden');
    clarifyingBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    announce('Please answer the clarifying questions to continue.');
  }

  function applyClarifyingAnswer(field, val) {
    if (field === 'guest_count') {
      const match = val.match(/\d+/);
      if (match) document.getElementById('guest-count').value = match[0];
    } else if (field === 'total_budget') {
      const clean = val.replace(/[^\d]/g, '');
      if (clean) {
        document.getElementById('total-budget').value = clean;
        budgetHint.textContent = formatIndianWords(parseInt(clean, 10));
      }
    } else if (field === 'event_type') {
      const lower = val.toLowerCase();
      if (lower.includes('wedding')) document.querySelector('input[name="event_type"][value="wedding"]').checked = true;
      if (lower.includes('birthday')) document.querySelector('input[name="event_type"][value="birthday"]').checked = true;
      if (lower.includes('community')) document.querySelector('input[name="event_type"][value="community"]').checked = true;
      if (lower.includes('anniversary')) document.querySelector('input[name="event_type"][value="anniversary"]').checked = true;
      if (lower.includes('corporate')) document.querySelector('input[name="event_type"][value="corporate"]').checked = true;
    }
    // Re-trigger submit to proceed
    form.dispatchEvent(new Event('submit'));
  }
}
