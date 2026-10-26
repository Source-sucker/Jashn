import { announce } from '../a11y.js';
import { postRefineIdeas } from '../api.js';
import { savePlan } from '../store.js';

export function renderIdeasView(container, plan) {
  container.textContent = '';

  const { ideas, brief } = plan;

  // Header
  const header = document.createElement('div');
  header.className = 'budget-overview-header';

  const hLeft = document.createElement('div');
  const title = document.createElement('h2');
  title.className = 'section-title';
  title.textContent = 'Curated Themes, Decor & Menus';

  const sub = document.createElement('p');
  sub.className = 'section-subtitle';
  sub.textContent = ideas.cultural_alignment_note || 'Personalized concepts tailored to your culture, dietary preferences, and budget tier.';
  hLeft.appendChild(title);
  hLeft.appendChild(sub);

  container.appendChild(header);

  // Themes Grid (3 concepts)
  const grid = document.createElement('div');
  grid.className = 'themes-grid';

  ideas.themes.forEach(theme => {
    const card = document.createElement('div');
    card.className = 'theme-card';

    const top = document.createElement('div');

    const badgeTier = document.createElement('span');
    badgeTier.className = `badge ${theme.estimated_tier === 'Budget-Friendly' ? 'badge-comfortable' : (theme.estimated_tier === 'Grand' ? 'badge-indigo' : 'badge-marigold')}`;
    badgeTier.textContent = theme.estimated_tier || 'Balanced';
    top.appendChild(badgeTier);

    const tTitle = document.createElement('h3');
    tTitle.style.fontSize = '1.3rem';
    tTitle.style.color = 'var(--indigo-900)';
    tTitle.style.margin = '0.5rem 0 0.25rem 0';
    tTitle.textContent = theme.title;
    top.appendChild(tTitle);

    const tagline = document.createElement('p');
    tagline.className = 'theme-tagline';
    tagline.textContent = theme.tagline;
    top.appendChild(tagline);

    const decorHeader = document.createElement('strong');
    decorHeader.style.display = 'block';
    decorHeader.style.fontSize = '0.9rem';
    decorHeader.style.marginTop = '0.75rem';
    decorHeader.textContent = '🌸 Decor & Ambience:';
    top.appendChild(decorHeader);

    const decorP = document.createElement('p');
    decorP.style.fontSize = '0.85rem';
    decorP.style.color = 'var(--text-secondary)';
    decorP.textContent = theme.decor_concept;
    top.appendChild(decorP);

    const menuHeader = document.createElement('strong');
    menuHeader.style.display = 'block';
    menuHeader.style.fontSize = '0.9rem';
    menuHeader.style.marginTop = '0.75rem';
    menuHeader.textContent = '🍲 Curated Menu Highlights:';
    top.appendChild(menuHeader);

    const menuUl = document.createElement('ul');
    menuUl.className = 'theme-details-list';
    theme.menu_highlights.forEach(m => {
      const li = document.createElement('li');
      li.textContent = `• ${m}`;
      menuUl.appendChild(li);
    });
    top.appendChild(menuUl);

    const actHeader = document.createElement('strong');
    actHeader.style.display = 'block';
    actHeader.style.fontSize = '0.9rem';
    actHeader.style.marginTop = '0.75rem';
    actHeader.textContent = '🎉 Guest Activities & Entertainment:';
    top.appendChild(actHeader);

    const actUl = document.createElement('ul');
    actUl.className = 'theme-details-list';
    theme.activities.forEach(a => {
      const li = document.createElement('li');
      li.textContent = `• ${a}`;
      actUl.appendChild(li);
    });
    top.appendChild(actUl);

    card.appendChild(top);

    const bottom = document.createElement('div');
    bottom.style.marginTop = '1rem';
    bottom.style.borderTop = '1px solid var(--border-subtle)';
    bottom.style.paddingTop = '0.75rem';

    const fitsBadge = document.createElement('span');
    fitsBadge.style.fontSize = '0.8rem';
    fitsBadge.style.fontWeight = '700';
    fitsBadge.style.color = theme.fits_allocation ? 'var(--emerald-600)' : 'var(--marigold-700)';
    fitsBadge.textContent = theme.fits_allocation ? '✓ Fits your budget allocation' : '⚠️ Requires higher allocation';
    bottom.appendChild(fitsBadge);

    card.appendChild(bottom);
    grid.appendChild(card);
  });

  container.appendChild(grid);

  // Refine Ideas Follow-Up Form
  const refineBox = document.createElement('div');
  refineBox.className = 'refine-ideas-box';

  const refTitle = document.createElement('h3');
  refTitle.className = 'card-title';
  refTitle.textContent = '✨ Refine These Ideas';
  refineBox.appendChild(refTitle);

  const refDesc = document.createElement('p');
  refDesc.style.fontSize = '0.9rem';
  refDesc.style.color = 'var(--text-secondary)';
  refDesc.style.marginBottom = '1rem';
  refDesc.textContent = 'Want different dishes, simpler flowers, or more elder-friendly games? Refine ideas without restarting your plan:';
  refineBox.appendChild(refDesc);

  const refForm = document.createElement('form');
  refForm.style.display = 'flex';
  refForm.style.gap = '0.75rem';
  refForm.style.flexWrap = 'wrap';

  refForm.innerHTML = `
    <input 
      type="text" 
      id="input-refine-ideas" 
      class="form-control" 
      style="flex: 1; min-width: 250px;" 
      placeholder="e.g. Too expensive, make decor sustainable and add live chaat counters..." 
      required
    >
    <button type="submit" id="btn-submit-refine" class="btn btn-primary">
      <span class="btn-text">Refine Ideas</span>
      <span class="btn-spinner hidden" aria-hidden="true"></span>
    </button>
  `;

  refForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = refForm.querySelector('#input-refine-ideas');
    const promptText = input.value.trim();
    if (!promptText) return;

    const btn = refForm.querySelector('#btn-submit-refine');
    const spinner = btn.querySelector('.btn-spinner');
    const bText = btn.querySelector('.btn-text');

    btn.disabled = true;
    spinner.classList.remove('hidden');
    bText.textContent = 'Refining...';
    announce('Refining theme ideas with your instructions...');

    try {
      const refinedReport = await postRefineIdeas({
        current_ideas: ideas,
        brief,
        refinement_prompt: promptText
      });

      plan.ideas = refinedReport;
      savePlan(plan);
      announce('Ideas successfully updated!');
      renderIdeasView(container, plan);
    } catch (err) {
      announce(`Error refining ideas: ${err.message}`, 'assertive');
      alert(`Could not refine ideas: ${err.message}`);
    } finally {
      btn.disabled = false;
      spinner.classList.add('hidden');
      bText.textContent = 'Refine Ideas';
    }
  });

  refineBox.appendChild(refForm);
  container.appendChild(refineBox);
}
