// Behaviour for the public landing page. Store links, contact details and the year are rendered by the server.
const CONFIG = { contactEmail: document.getElementById('quote-form')?.dataset.contactEmail || '', formEndpoint: '' };

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

// Quote form
const form = document.getElementById('quote-form');
if (!CONFIG.formEndpoint && !CONFIG.contactEmail) {
  form.insertAdjacentHTML('afterbegin', '<p class="rounded-xl border border-line px-3 py-3 text-sm text-muted">Online quote requests open soon.</p>');
  form.querySelectorAll('input, textarea, button').forEach(el => el.disabled = true);
  form.querySelector('[type=submit]').classList.replace('disabled:animate-pulse', 'disabled:opacity-50');
}
const showErr = (input, msg) => {
  const el = input.closest('label').querySelector('.err');
  el.textContent = msg; el.classList.toggle('hidden', !msg);
  input.setAttribute('aria-invalid', !!msg);
  input.classList.toggle('!border-brand', !!msg);
};
const validate = input => {
  const v = input.value.trim();
  if (input.required && !v) return showErr(input, 'This field is required.'), false;
  if (input.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) return showErr(input, 'Enter an email like name@company.com.'), false;
  return showErr(input, ''), true;
};
form.querySelectorAll('[required]').forEach(i => i.addEventListener('blur', () => validate(i)));
form.addEventListener('submit', async e => {
  e.preventDefault();
  const fields = [...form.querySelectorAll('[required]')];
  const ok = fields.map(validate).every(Boolean);
  if (!ok) return fields.find(f => f.getAttribute('aria-invalid') === 'true').focus();

  const data = new FormData(form);
  const formErr = document.getElementById('form-error');
  const submit = form.querySelector('[type=submit]');
  formErr.classList.add('hidden');
  submit.disabled = true; submit.firstChild.textContent = 'Sending your request ';
  try {
    const done = document.getElementById("form-done");
    if (CONFIG.formEndpoint) {
      const res = await fetch(CONFIG.formEndpoint, { method: 'POST', body: data, headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error();
      done.querySelector('[data-done-name]').textContent = data.get('name').trim().split(' ')[0];
      done.querySelector('[data-done-email]').textContent = data.get('email');
    } else if (CONFIG.contactEmail) {
      const body = [...data].map(([k, v]) => `${k}: ${v}`).join('\n');
      done.querySelector("h3").textContent = "Almost there. Send the email.";
      done.querySelector("p").textContent = `Your email app has opened with your request addressed to ${CONFIG.contactEmail}. Press send and we will reply with next steps.`;
      location.href = `mailto:${CONFIG.contactEmail}?subject=${encodeURIComponent('Quote request from ' + data.get('name'))}&body=${encodeURIComponent(body)}`;
    } else throw new Error('unconfigured');
    form.classList.add('hidden');
    done.classList.replace('hidden', 'flex'); done.focus();
  } catch (err) {
    formErr.textContent = err.message === 'unconfigured'
      ? 'Online quote requests are not available yet. Please try again soon.'
      : 'We could not send your request. Check your connection and try again.';
    formErr.classList.remove('hidden');
  } finally {
    submit.disabled = false; submit.firstChild.textContent = 'Request a quote ';
  }
});

// FAQ schema for search and answer engines, built from the visible FAQ
const faq = { '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: [...document.querySelectorAll('#faq-list details')].map(d => ({
  '@type': 'Question', name: d.querySelector('summary').textContent.trim(),
  acceptedAnswer: { '@type': 'Answer', text: d.querySelector('p').textContent.trim() }
})) };
const ld = document.createElement('script'); ld.type = 'application/ld+json'; ld.textContent = JSON.stringify(faq); document.head.append(ld);
