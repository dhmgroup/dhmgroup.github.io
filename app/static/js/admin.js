// Admin behaviour: toasts raised by HX-Trigger {"toast": "..."} and focus after htmx swaps.
const toasts = document.getElementById('toasts');
document.addEventListener('toast', e => {
  const el = document.createElement('p');
  el.className = 'pointer-events-auto rounded-xl border border-line bg-raised px-4 py-3 text-sm shadow-lg transition-opacity duration-200';
  el.textContent = e.detail.value;
  toasts.append(el);
  setTimeout(() => { el.classList.add('opacity-0'); setTimeout(() => el.remove(), 200); }, 4000);
});
document.addEventListener('htmx:after:settle', e => {
  e.target.querySelector?.('[data-autofocus]')?.focus();
});
const toast = value => document.dispatchEvent(new CustomEvent('toast', { detail: { value } }));
document.addEventListener('htmx:error', () => toast('Something went wrong. Check your connection and try again.'));
document.addEventListener('htmx:response:error', e => {
  const status = e.detail.ctx.response.status;
  if (status === 403) toast('Your session changed. Reload the page and try again.');
  else if (status === 404) toast('That lead no longer exists. Reload the page.');
  else if (status >= 500) toast('Something went wrong on our side. Try again in a minute.');
});

// Mark the open lead's row in the list: after panel swaps, list refreshes and on first load.
const markCurrentRow = () => {
  const id = location.pathname.match(/^\/admin\/inquiries\/(\d+)/)?.[1];
  document.querySelectorAll('#inquiry-list a[data-inquiry-id]').forEach(a => {
    if (a.dataset.inquiryId === id) a.setAttribute('aria-current', 'true');
    else a.removeAttribute('aria-current');
  });
};
markCurrentRow();
document.addEventListener('htmx:after:settle', markCurrentRow);
