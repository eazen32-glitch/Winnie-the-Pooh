const editor = document.querySelector('#edit-dialog');
document.querySelectorAll('[data-edit]').forEach(button => {
  button.addEventListener('click', () => editor.showModal());
});
document.querySelectorAll('[data-close]').forEach(button => {
  button.addEventListener('click', () => button.closest('dialog').close());
});
document.querySelectorAll('[data-project]').forEach(button => {
  button.addEventListener('click', () => {
    document.getElementById(`project-${button.dataset.project}`).showModal();
  });
});
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
});
if (editor.dataset.open === 'true') {
  editor.showModal();
  editor.querySelector('[aria-invalid="true"]')?.focus();
}
const links = [...document.querySelectorAll('.nav-link')];
const observer = new IntersectionObserver(entries => {
  const visible = entries.filter(entry => entry.isIntersecting);
  if (!visible.length) return;
  const id = visible[0].target.id;
  links.forEach(link => {
    const active = link.hash === `#${id}`;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
}, { rootMargin: '-10% 0px -50% 0px', threshold: 0 });
document.querySelectorAll('#overview, #work, #about').forEach(section => observer.observe(section));


// Repeatable Year / Details tables.
document.querySelectorAll('[data-profile-table]').forEach(section => {
  const rows = section.querySelector('[data-table-rows]');
  const template = section.querySelector('[data-table-row-template]');
  const addButton = section.querySelector('[data-add-table-row]');
  const status = section.querySelector('.history-row-status');
  const maximum = section.dataset.maxRows ? Number(section.dataset.maxRows) : Infinity;

  function updateStatus() {
    const count = rows.children.length;
    addButton.disabled = count >= maximum;
    status.textContent = Number.isFinite(maximum)
      ? `${count} of ${maximum} rows${count >= maximum ? ' — maximum reached' : ''}`
      : `${count} ${count === 1 ? 'row' : 'rows'}`;
    [...rows.children].forEach((row, index) => {
      row.querySelector('[data-remove-table-row]').setAttribute(
        'aria-label', `Remove ${section.querySelector('h3').textContent.toLowerCase()} row ${index + 1}`
      );
    });
  }

  function updateRequired(row) {
    const year = row.querySelector('select');
    const details = row.querySelector('textarea');
    const hasContent = Boolean(year.value || details.value.trim());
    year.required = hasContent;
    details.required = hasContent;
  }

  addButton.addEventListener('click', () => {
    if (rows.children.length >= maximum) return;
    rows.append(template.content.cloneNode(true));
    updateStatus();
    rows.lastElementChild.querySelector('select').focus();
  });

  section.addEventListener('click', event => {
    const button = event.target.closest('[data-remove-table-row]');
    if (!button) return;
    const row = button.closest('tr');
    const next = row.nextElementSibling || row.previousElementSibling;
    row.remove();
    updateStatus();
    if (next) next.querySelector('select').focus();
    else addButton.focus();
  });

  ['input', 'change'].forEach(eventName => {
    rows.addEventListener(eventName, event => {
      const row = event.target.closest('tr');
      if (row) updateRequired(row);
    });
  });
  [...rows.children].forEach(updateRequired);
  updateStatus();
});
