/* StrokesEdge on-site newsletter signup.
   Substack stays the list and the sender. This script puts its official embedded signup form
   inside a dialog (any element with data-signup) or inline (any element with data-signup-inline),
   so visitors subscribe without leaving strokesedge.com. Elements keep their normal href, so the
   link still works with JavaScript off. Deep link: /#subscribe opens the dialog.
   Config below. */
(function () {
  'use strict';
  var SUBSTACK = 'https://strokesedge.substack.com';
  var EMBED = SUBSTACK + '/embed';
  /* Set to false until the Substack welcome email actually contains the cheat sheet link. */
  var CHEAT_SHEET_IN_WELCOME = true;

  var css = [
    '.se-dlg{border:1px solid rgba(0,230,118,.35);background:#0d1a14;color:#e8efe9;padding:0;width:min(520px,calc(100vw - 24px));max-height:calc(100vh - 24px);overflow:auto;border-radius:4px;font-family:Outfit,Helvetica Neue,sans-serif;font-weight:300}',
    '.se-dlg::backdrop{background:rgba(3,6,4,.82)}',
    '.se-dlg-in{padding:28px 26px 24px}',
    '.se-dlg h2{margin:0 0 10px;font:800 30px/1 Archivo,Arial,sans-serif;font-stretch:108%;letter-spacing:-.02em;text-transform:none}',
    '.se-dlg h2 em{font:italic 400 1.05em/1 "Instrument Serif",Georgia,serif;color:#00e676;letter-spacing:0}',
    '.se-dlg p{margin:0 0 16px;font-size:16px;line-height:1.6;color:#b9c9bf}',
    '.se-dlg .se-x{position:absolute;right:10px;top:8px;background:none;border:0;color:#8da398;font:400 26px/1 Outfit,sans-serif;cursor:pointer;padding:8px 12px}',
    '.se-dlg .se-x:hover{color:#e8efe9}',
    '.se-frame{display:block;width:100%;height:430px;border:0;background:#fff;border-radius:2px}',
    '.se-dlg .se-alt{margin:14px 0 0;font:400 12px/1.5 "DM Mono",monospace;letter-spacing:.06em;color:#8da398}',
    '.se-dlg .se-alt a{color:#00e676}',
    '.se-inline{background:#fff;border-radius:2px;min-height:430px}',
    '.se-inline .se-frame{height:430px}',
    '@media(max-width:640px){.se-dlg-in{padding:24px 16px 18px}.se-frame,.se-inline,.se-inline .se-frame{height:470px;min-height:470px}}'
  ].join('');
  var st = document.createElement('style');
  st.textContent = css;
  document.head.appendChild(st);

  function track(name, params) {
    try { if (typeof window.gtag === 'function') window.gtag('event', name, params || {}); } catch (e) {}
  }

  function frame(host) {
    if (host.querySelector('iframe')) return;
    var f = document.createElement('iframe');
    f.className = 'se-frame';
    f.src = EMBED;
    f.title = 'Subscribe to the StrokesEdge newsletter';
    f.setAttribute('loading', 'lazy');
    f.setAttribute('scrolling', 'no');
    host.appendChild(f);
  }

  var dlg = null;
  function build() {
    dlg = document.createElement('dialog');
    dlg.className = 'se-dlg';
    dlg.setAttribute('aria-label', 'Subscribe to the StrokesEdge newsletter');
    dlg.innerHTML =
      '<div class="se-dlg-in">' +
      '<button class="se-x" type="button" aria-label="Close">×</button>' +
      '<h2>Get the free <em>weekly picks.</em></h2>' +
      '<p>One email before each PGA Tour event: the strokes gained model’s picks, the course breakdown and the stats that matter.' +
      (CHEAT_SHEET_IN_WELCOME ? ' Your welcome email includes the free strokes gained cheat sheet.' : '') + '</p>' +
      '<div class="se-slot"></div>' +
      '<p class="se-alt">Free. Unsubscribe any time. Or <a href="' + SUBSTACK + '" target="_blank" rel="noopener">open it on Substack</a>.</p>' +
      '</div>';
    document.body.appendChild(dlg);
    dlg.querySelector('.se-x').addEventListener('click', function () { dlg.close(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener('close', function () {
      if (location.hash === '#subscribe' && history.replaceState) history.replaceState(null, '', location.pathname + location.search);
    });
  }

  function open(source) {
    if (typeof HTMLDialogElement === 'undefined') { window.open(SUBSTACK, '_blank', 'noopener'); return; }
    if (!dlg) build();
    frame(dlg.querySelector('.se-slot'));
    if (!dlg.open) dlg.showModal();
    track('signup_open', { source: source || 'unknown', page: location.pathname });
  }

  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-signup]') : null;
    if (!el || e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    open(el.getAttribute('data-signup') || el.textContent.trim().slice(0, 30));
  });

  function inline() {
    var hosts = document.querySelectorAll('[data-signup-inline]');
    if (!hosts.length) return;
    hosts.forEach(function (h) { h.classList.add('se-inline'); });
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) { frame(en.target); io.unobserve(en.target); }
        });
      }, { rootMargin: '300px' });
      hosts.forEach(function (h) { io.observe(h); });
    } else {
      hosts.forEach(frame);
    }
  }

  function init() {
    inline();
    if (location.hash === '#subscribe') open('hash');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  window.addEventListener('hashchange', function () { if (location.hash === '#subscribe') open('hash'); });
})();
