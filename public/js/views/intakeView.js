import { announce, formatIndianWords } from '../a11y.js';
import { postIntake, postPlan } from '../api.js';
import { savePlan } from '../store.js';

export function extractDetailsFromText(text) {
  if (!text || typeof text !== 'string') return {};
  const lower = text.toLowerCase();
  const extracted = {};

  // 1. Event Type
  if (/\b(wedding|shaadi|shadi|vivaah|marriage|reception|sangeet|mehendi|haldi|baraat)\b/i.test(lower)) {
    extracted.event_type = 'wedding';
  } else if (/\b(birthday|bday|janamdin)\b/i.test(lower)) {
    extracted.event_type = 'birthday';
  } else if (/\b(anniversary|salgirah)\b/i.test(lower)) {
    extracted.event_type = 'anniversary';
  } else if (/\b(community|puja|pooja|festival|diwali|navratri|durga|ganesh|samajik|jagran)\b/i.test(lower)) {
    extracted.event_type = 'community';
  } else if (/\b(corporate|annual meet|conference|seminar|office party|retreat)\b/i.test(lower)) {
    extracted.event_type = 'corporate';
  }

  // 2. Guest Count
  const guestMatch = text.match(/(?:for|with|around|approx|approximately)?\s*(\d{1,5})\s*(?:guests?|people|attendees?|pax|persons?|members?|baraatis?|kids?|children)/i)
    || text.match(/(?:guests?|attendees?|pax|people|kids?|children)\s*(?:of|around|approx|count|:)?\s*(\d{1,5})/i);
  if (guestMatch) {
    const count = parseInt(guestMatch[1], 10);
    if (count > 0) extracted.guest_count = count;
  }

  // 3. Total Budget in INR
  const croreMatch = text.match(/(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:crores?|crs?|cr)\b/i);
  const lakhMatch = text.match(/(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lac|l)\b/i);
  const thousandMatch = text.match(/(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:k|thousand)\b/i);
  const budgetPrefixMatch = text.match(/(?:budget\s*(?:of|is|:)?\s*)(?:₹|rs\.?|inr)?\s*(\d[\d,]+)/i);
  const budgetSuffixMatch = text.match(/(\d[\d,]+)\s*(?:budget|inr|rs|rupees)/i);
  const directCurrencyMatch = text.match(/(?:₹|rs\.?)\s*(\d[\d,]+)/i);

  if (croreMatch) {
    extracted.total_budget = Math.round(parseFloat(croreMatch[1]) * 10000000);
  } else if (lakhMatch) {
    extracted.total_budget = Math.round(parseFloat(lakhMatch[1]) * 100000);
  } else if (thousandMatch) {
    extracted.total_budget = Math.round(parseFloat(thousandMatch[1]) * 1000);
  } else if (budgetPrefixMatch) {
    const clean = parseInt(budgetPrefixMatch[1].replace(/,/g, ''), 10);
    if (clean >= 5000) extracted.total_budget = clean;
  } else if (budgetSuffixMatch) {
    const clean = parseInt(budgetSuffixMatch[1].replace(/,/g, ''), 10);
    if (clean >= 5000) extracted.total_budget = clean;
  } else if (directCurrencyMatch) {
    const clean = parseInt(directCurrencyMatch[1].replace(/,/g, ''), 10);
    if (clean >= 5000) extracted.total_budget = clean;
  }

  // 4. City
  const knownCities = [
    'Lucknow', 'Jaipur', 'Delhi', 'New Delhi', 'Mumbai', 'Bengaluru', 'Bangalore',
    'Kolkata', 'Hyderabad', 'Chennai', 'Pune', 'Ahmedabad', 'Chandigarh', 'Udaipur',
    'Agra', 'Varanasi', 'Indore', 'Bhopal', 'Goa', 'Surat', 'Patna', 'Kanpur',
    'Nagpur', 'Vadodara', 'Ghaziabad', 'Ludhiana', 'Nashik', 'Faridabad', 'Meerut',
    'Rajkot', 'Kochi', 'Coimbatore', 'Amritsar', 'Dehradun', 'Jodhpur', 'Shimla',
    'Noida', 'Gurgaon', 'Gurugram'
  ];
  for (const c of knownCities) {
    const rx = new RegExp(`\\b${c}\\b`, 'i');
    if (rx.test(text)) {
      extracted.city = c;
      break;
    }
  }
  if (!extracted.city) {
    const inCityMatch = text.match(/\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b/);
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    if (inCityMatch && !monthNames.includes(inCityMatch[1])) {
      extracted.city = inCityMatch[1];
    }
  }

  // 5. Date / Month
  const months = [
    { name: 'january', num: 0 }, { name: 'february', num: 1 }, { name: 'march', num: 2 },
    { name: 'april', num: 3 }, { name: 'may', num: 4 }, { name: 'june', num: 5 },
    { name: 'july', num: 6 }, { name: 'august', num: 7 }, { name: 'september', num: 8 },
    { name: 'october', num: 9 }, { name: 'november', num: 10 }, { name: 'december', num: 11 },
    { name: 'jan', num: 0 }, { name: 'feb', num: 1 }, { name: 'mar', num: 2 },
    { name: 'apr', num: 3 }, { name: 'jun', num: 5 }, { name: 'jul', num: 6 },
    { name: 'aug', num: 7 }, { name: 'sep', num: 8 }, { name: 'sept', num: 8 },
    { name: 'oct', num: 9 }, { name: 'nov', num: 10 }, { name: 'dec', num: 11 }
  ];

  const inMonthsMatch = text.match(/\bin\s*(\d+)\s*months?\b/i);
  const nextMonthMatch = /\bnext\s+month\b/i.test(text);

  if (inMonthsMatch) {
    const d = new Date();
    d.setMonth(d.getMonth() + parseInt(inMonthsMatch[1], 10));
    extracted.event_date = d.toISOString().split('T')[0];
  } else if (nextMonthMatch) {
    const d = new Date();
    d.setMonth(d.getMonth() + 1);
    extracted.event_date = d.toISOString().split('T')[0];
  } else {
    for (const m of months) {
      const rx = new RegExp(`\\b${m.name}\\b`, 'i');
      if (rx.test(lower)) {
        const d = new Date();
        const currentYear = d.getFullYear();
        const currentMonth = d.getMonth();
        let targetYear = currentYear;
        if (m.num <= currentMonth) {
          targetYear += 1;
        }
        const targetDate = new Date(Date.UTC(targetYear, m.num, 15));
        extracted.event_date = targetDate.toISOString().split('T')[0];
        break;
      }
    }
  }

  return extracted;
}

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
  const descInput = document.getElementById('event-description');
  const smartExtractHint = document.getElementById('smart-extract-hint');

  // Real-time Natural Language Extraction & Auto-fill
  function updateExtractionFromDescription() {
    if (!descInput) return;
    const text = descInput.value.trim();
    if (!text) {
      if (smartExtractHint) {
        smartExtractHint.classList.add('hidden');
        smartExtractHint.innerHTML = '';
      }
      return;
    }
    const detected = extractDetailsFromText(text);
    const chips = [];

    if (detected.event_type) {
      const radio = form.querySelector(`input[name="event_type"][value="${detected.event_type}"]`);
      if (radio && !radio.checked) {
        radio.checked = true;
      }
      const emojiMap = { wedding: '💍', birthday: '🎂', community: '🪔', anniversary: '🥂', corporate: '👔' };
      chips.push(`<span class="extract-chip">${emojiMap[detected.event_type] || '🎉'} ${detected.event_type}</span>`);
    }

    if (detected.guest_count) {
      const gInput = document.getElementById('guest-count');
      if (gInput && (!gInput.value || gInput.value !== String(detected.guest_count))) {
        gInput.value = detected.guest_count;
      }
      chips.push(`<span class="extract-chip">👥 ${detected.guest_count} guests</span>`);
    }

    if (detected.total_budget) {
      if (budgetInput && (!budgetInput.value || budgetInput.value !== String(detected.total_budget))) {
        budgetInput.value = detected.total_budget;
        budgetHint.textContent = formatIndianWords(detected.total_budget);
      }
      chips.push(`<span class="extract-chip">💰 ₹${detected.total_budget.toLocaleString('en-IN')}</span>`);
    }

    if (detected.city) {
      const cInput = document.getElementById('event-city');
      if (cInput && (!cInput.value || cInput.value !== detected.city)) {
        cInput.value = detected.city;
      }
      chips.push(`<span class="extract-chip">📍 ${detected.city}</span>`);
    }

    if (detected.event_date) {
      const dInput = document.getElementById('event-date');
      if (dInput && (!dInput.value || dInput.value !== detected.event_date)) {
        dInput.value = detected.event_date;
      }
      chips.push(`<span class="extract-chip">📅 ${detected.event_date}</span>`);
    }

    if (smartExtractHint) {
      if (chips.length > 0) {
        smartExtractHint.innerHTML = `<span class="extract-title">✨ Auto-Detected:</span>` + chips.join(' ');
        smartExtractHint.classList.remove('hidden');
      } else {
        smartExtractHint.classList.add('hidden');
      }
    }
  }

  let descDebounceTimer = null;
  if (descInput) {
    descInput.addEventListener('input', () => {
      clearTimeout(descDebounceTimer);
      descDebounceTimer = setTimeout(updateExtractionFromDescription, 120);
    });
    descInput.addEventListener('blur', updateExtractionFromDescription);
  }

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

  let submitProgressInterval = null;
  function setLoading(loading) {
    if (loading) {
      btnSubmit.disabled = true;
      submitSpinner.classList.remove('hidden');
      submitText.textContent = '1/2 Analyzing celebration details...';
      let step = 1;
      submitProgressInterval = setInterval(() => {
        step = (step % 2) + 1;
        if (step === 2) {
          submitText.textContent = '2/2 Structuring budget & timeline...';
        }
      }, 1200);
    } else {
      if (submitProgressInterval) clearInterval(submitProgressInterval);
      btnSubmit.disabled = false;
      submitSpinner.classList.add('hidden');
      submitText.textContent = 'Build My Celebration Plan';
    }
  }

  // Form Submit Handler
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();

    // Ensure any freshly typed/pasted text is parsed and auto-filled
    updateExtractionFromDescription();

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

      // Intake complete: generate plan progressively!
      clarifyingBox.classList.add('hidden');
      announce('Calculating budget and timeline...', 'polite');

      // Return deterministic budget and timeline immediately
      const planRes = await postPlan(brief, false);
      planRes.ai_pending = true;

      savePlan(planRes);
      setLoading(false);
      announce('Budget and timeline ready! Loading your celebration dashboard.', 'polite');
      if (onPlanGenerated) onPlanGenerated(planRes, { progressive: true, brief });
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
