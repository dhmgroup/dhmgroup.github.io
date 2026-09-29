// Behaviour for the public landing page. Store links, contact details and the year are rendered by the server.

// Mobile menu
const btn = document.getElementById('menu-btn'), menu = document.getElementById('menu');
const setMenu = open => {
  btn.setAttribute('aria-expanded', open);
  btn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  menu.setAttribute('aria-hidden', !open);
  menu.classList.toggle('opacity-0', !open);
  menu.classList.toggle('pointer-events-none', !open);
  btn.querySelector('.bar-a').classList.toggle('!top-5', open);
  btn.querySelector('.bar-a').classList.toggle('rotate-45', open);
  btn.querySelector('.bar-b').classList.toggle('!top-5', open);
  btn.querySelector('.bar-b').classList.toggle('-rotate-45', open);
  menu.querySelectorAll('.menu-item').forEach(li => { li.classList.toggle('translate-y-12', !open); li.classList.toggle('opacity-0', !open); });
  document.body.style.overflow = open ? 'hidden' : '';
};
btn.addEventListener('click', () => setMenu(btn.getAttribute('aria-expanded') !== 'true'));
menu.addEventListener('click', e => e.target.closest('a') && setMenu(false));
addEventListener('keydown', e => e.key === 'Escape' && setMenu(false));

// Scroll reveals
const io = new IntersectionObserver(entries => entries.forEach(e => {
  if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
}), { rootMargin: '0px 0px -10% 0px' });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));

// Current section in nav
const links = [...document.querySelectorAll('[data-nav]')];
const navIO = new IntersectionObserver(entries => entries.forEach(e => {
  if (e.isIntersecting) links.forEach(l => l.setAttribute('aria-current', l.hash === '#' + e.target.id));
}), { rootMargin: '-45% 0px -50% 0px' });
['services', 'apps', 'process', 'faq', 'quote'].forEach(id => navIO.observe(document.getElementById(id)));

// Tagline: words light up one at a time as they cross the trigger line
const tag = document.querySelector('[data-words]');
tag.innerHTML = tag.innerHTML.split(/(<br[^>]*>)/).map(part =>
  part.startsWith('<br') ? part : part.split(/(\s+)/).map(w => w.trim() ? `<span class="word">${w}</span>` : w).join('')
).join('');
const words = [...tag.querySelectorAll('.word')], swash = document.querySelector('.swash');
let ticking = false;
const paint = () => {
  ticking = false;
  const line = innerHeight * 0.65;
  words.forEach(w => w.classList.toggle('lit', w.getBoundingClientRect().top < line));
  if (words.at(-1).classList.contains('lit')) swash.classList.add('in');
};
addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(paint); } }, { passive: true });
paint();

// Quote form: htmx posts it and swaps the server-rendered form or confirmation into #quote-panel.
const panel = document.getElementById('quote-panel');
const showFormError = msg => {
  const el = panel.querySelector('#form-error');
  if (el) { el.textContent = msg; el.classList.remove('hidden'); }
};
panel.addEventListener('htmx:after:settle', () => {
  (panel.querySelector('#form-done') || panel.querySelector('[aria-invalid="true"]'))?.focus();
});
panel.addEventListener('htmx:response:error', e => {
  if (e.detail.ctx.response.status >= 500) showFormError('We could not send your request. Please try again in a minute.');
});
panel.addEventListener('htmx:error', () => showFormError('We could not send your request. Check your connection and try again.'));
