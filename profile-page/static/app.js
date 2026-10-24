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


// Frontend-only PDF demo. This input has no name and sends no files to Flask.
document.querySelectorAll('[data-pdf-demo]').forEach(section => {
  const input = section.querySelector('input[type="file"]');
  const list = section.querySelector('[data-pdf-demo-files]');
  const status = section.querySelector('.pdf-demo-status');
  const error = section.querySelector('#pdf-demo-error');
  let selected = [];

  function renderFiles() {
    list.replaceChildren();
    selected.forEach((file, index) => {
      const item = document.createElement('li');
      item.className = 'pdf-demo-file';
      const badge = document.createElement('span');
      badge.className = 'pdf-demo-file-badge';
      badge.textContent = 'PDF';
      badge.setAttribute('aria-hidden', 'true');
      const info = document.createElement('div');
      info.className = 'pdf-demo-file-info';
      const name = document.createElement('strong');
      name.textContent = file.name;
      const size = document.createElement('small');
      size.textContent = `${(file.size / 1024).toFixed(1)} KB · Demo selection`;
      info.append(name, size);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'pdf-demo-remove';
      remove.textContent = 'Remove';
      remove.setAttribute('aria-label', `Remove ${file.name}`);
      remove.addEventListener('click', () => {
        selected.splice(index, 1);
        error.hidden = true;
        renderFiles();
        const nextRemove = list.querySelectorAll('button')[Math.min(index, selected.length - 1)];
        if (nextRemove) nextRemove.focus();
        else input.focus();
      });
      item.append(badge, info, remove);
      list.append(item);
    });
    status.textContent = selected.length
      ? `${selected.length} ${selected.length === 1 ? 'PDF' : 'PDFs'} selected for this demo.`
      : 'No PDFs selected.';
  }

  input.addEventListener('change', () => {
    const incoming = [...input.files];
    const combined = [...selected];
    let message = '';
    for (const file of incoming) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        message = 'Choose PDF files for this demo.';
        break;
      }
      if (file.size > 5 * 1024 * 1024) {
        message = `${file.name} is larger than 5 MB.`;
        break;
      }
      const duplicate = combined.some(existing => existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified);
      if (!duplicate) combined.push(file);
    }
    if (!message && combined.length > 10) message = 'Select up to 10 PDFs for this demo.';
    error.textContent = message;
    error.hidden = !message;
    if (!message) selected = combined;
    input.value = '';
    renderFiles();
  });
});
