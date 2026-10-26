import { announce, formatINR } from '../a11y.js';
import { savePlan } from '../store.js';

export function renderVendorsView(container, plan) {
  container.textContent = '';

  const { vendors } = plan;

  // Header & Disclaimer
  const header = document.createElement('div');
  header.className = 'budget-overview-header';

  const hLeft = document.createElement('div');
  const title = document.createElement('h2');
  title.className = 'section-title';
  title.textContent = 'Vendor Checklist & Quote Comparison';

  const sub = document.createElement('p');
  sub.className = 'section-subtitle';
  sub.textContent = 'Curated questions to ask prospective vendors and a private quote tracker. All budget values are estimates.';
  hLeft.appendChild(title);
  hLeft.appendChild(sub);

  container.appendChild(header);

  // Mandatory Safety Disclaimer
  const disclaimer = document.createElement('div');
  disclaimer.className = 'clarifying-box';
  disclaimer.style.background = 'var(--indigo-50)';
  disclaimer.style.borderColor = 'var(--indigo-300)';
  disclaimer.innerHTML = `
    <strong>🛡️ Important Vendor Principle:</strong> Jashn provides category checklists and questions to ask. 
    Jashn <em>never</em> invents business names, phone numbers, or claims availability. 
    You enter real quotes from vendors you contact to compare against your code-allocated budget ceiling.
  `;
  container.appendChild(disclaimer);

  // Vendor Categories List
  vendors.forEach(cat => {
    const card = document.createElement('div');
    card.className = 'vendor-card';

    // Header: Category Title + Estimate
    const cHead = document.createElement('div');
    cHead.className = 'vendor-card-header';

    const cTitle = document.createElement('h3');
    cTitle.style.color = 'var(--indigo-900)';
    cTitle.style.fontSize = '1.2rem';
    cTitle.textContent = cat.name;

    const cEst = document.createElement('div');
    cEst.style.fontSize = '1rem';
    cEst.style.fontWeight = '700';
    cEst.style.color = 'var(--marigold-700)';
    cEst.textContent = `Category Estimate: ${formatINR(cat.estimated_budget)}`;

    cHead.appendChild(cTitle);
    cHead.appendChild(cEst);
    card.appendChild(cHead);

    // Questions to ask
    const qTitle = document.createElement('h4');
    qTitle.style.fontSize = '0.95rem';
    qTitle.style.fontWeight = '700';
    qTitle.style.color = 'var(--text-primary)';
    qTitle.style.marginBottom = '0.4rem';
    qTitle.textContent = '💡 Critical Questions to Ask:';
    card.appendChild(qTitle);

    const qList = document.createElement('ul');
    qList.className = 'questions-list';
    cat.questions_to_ask.forEach(q => {
      const li = document.createElement('li');
      li.textContent = q;
      qList.appendChild(li);
    });
    card.appendChild(qList);

    // Logged Quotes List
    const quotesTitle = document.createElement('h4');
    quotesTitle.style.fontSize = '0.95rem';
    quotesTitle.style.fontWeight = '700';
    quotesTitle.style.color = 'var(--text-primary)';
    quotesTitle.style.marginBottom = '0.5rem';
    quotesTitle.textContent = '📝 Quotes Received:';
    card.appendChild(quotesTitle);

    const quotesContainer = document.createElement('div');
    quotesContainer.className = 'user-vendors-list';

    if (!cat.user_vendors || cat.user_vendors.length === 0) {
      const emptyNote = document.createElement('p');
      emptyNote.style.fontSize = '0.85rem';
      emptyNote.style.color = 'var(--text-muted)';
      emptyNote.style.marginBottom = '1rem';
      emptyNote.textContent = 'No quotes recorded yet for this category.';
      quotesContainer.appendChild(emptyNote);
    } else {
      cat.user_vendors.forEach((uv, idx) => {
        const uvItem = document.createElement('div');
        uvItem.className = 'user-vendor-item';

        const uvInfo = document.createElement('div');
        const uvName = document.createElement('strong');
        uvName.textContent = uv.name;
        const uvQuote = document.createElement('span');
        uvQuote.style.marginLeft = '0.5rem';
        uvQuote.style.fontWeight = '700';
        uvQuote.textContent = uv.quote_amount ? formatINR(uv.quote_amount) : 'Quote Pending';

        const uvDiff = document.createElement('span');
        uvDiff.style.fontSize = '0.8rem';
        uvDiff.style.marginLeft = '0.5rem';
        if (uv.quote_amount && cat.estimated_budget) {
          const diff = uv.quote_amount - cat.estimated_budget;
          if (diff > 0) {
            uvDiff.style.color = 'var(--rose-600)';
            uvDiff.textContent = `(+${formatINR(diff)} over est)`;
          } else {
            uvDiff.style.color = 'var(--emerald-600)';
            uvDiff.textContent = `(${formatINR(diff)} under est)`;
          }
        }

        const uvMeta = document.createElement('div');
        uvMeta.style.fontSize = '0.8rem';
        uvMeta.style.color = 'var(--text-secondary)';
        uvMeta.textContent = `Status: ${uv.status} • Contact: ${uv.contact || 'N/A'} • ${uv.notes || ''}`;

        uvInfo.appendChild(uvName);
        uvInfo.appendChild(uvQuote);
        uvInfo.appendChild(uvDiff);
        uvInfo.appendChild(uvMeta);

        const btnRemove = document.createElement('button');
        btnRemove.type = 'button';
        btnRemove.className = 'btn btn-ghost text-danger';
        btnRemove.style.padding = '0.2rem 0.5rem';
        btnRemove.textContent = 'Delete';
        btnRemove.addEventListener('click', () => {
          cat.user_vendors.splice(idx, 1);
          savePlan(plan);
          announce(`Removed quote for ${uv.name}`);
          renderVendorsView(container, plan);
        });

        uvItem.appendChild(uvInfo);
        uvItem.appendChild(btnRemove);
        quotesContainer.appendChild(uvItem);
      });
    }
    card.appendChild(quotesContainer);

    // Add Vendor Quote Form
    const addForm = document.createElement('form');
    addForm.style.marginTop = '1rem';
    addForm.style.display = 'grid';
    addForm.style.gridTemplateColumns = 'repeat(auto-fit, minmax(180px, 1fr)) auto';
    addForm.style.gap = '0.5rem';
    addForm.style.alignItems = 'end';

    addForm.innerHTML = `
      <div>
        <label class="form-label" style="font-size: 0.8rem;">Vendor Name</label>
        <input type="text" name="name" class="form-control" placeholder="e.g. Anand Caterers" required>
      </div>
      <div>
        <label class="form-label" style="font-size: 0.8rem;">Phone / Contact</label>
        <input type="text" name="contact" class="form-control" placeholder="e.g. 98XXXXXXXX">
      </div>
      <div>
        <label class="form-label" style="font-size: 0.8rem;">Quoted Amount (INR)</label>
        <input type="number" name="quote" class="form-control" placeholder="e.g. 150000" min="0" step="500">
      </div>
      <div>
        <label class="form-label" style="font-size: 0.8rem;">Status</label>
        <select name="status" class="form-control">
          <option value="pending">Pending</option>
          <option value="shortlisted" selected>Shortlisted</option>
          <option value="confirmed">Confirmed</option>
        </select>
      </div>
      <button type="submit" class="btn btn-primary" style="padding: 0.65rem 1rem;">
        + Add Quote
      </button>
    `;

    addForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const fData = new FormData(addForm);
      const name = fData.get('name').trim();
      const contact = fData.get('contact').trim();
      const quote = parseInt(fData.get('quote'), 10) || null;
      const status = fData.get('status');

      if (!name) return;

      if (!cat.user_vendors) cat.user_vendors = [];
      cat.user_vendors.push({
        id: `uv_${Date.now()}`,
        category_id: cat.category_id,
        name,
        contact,
        quote_amount: quote,
        status,
        notes: ''
      });

      savePlan(plan);
      announce(`Added quote from ${name}`);
      renderVendorsView(container, plan);
    });

    card.appendChild(addForm);
    container.appendChild(card);
  });
}
