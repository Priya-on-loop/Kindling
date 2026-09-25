/* =========================================================
   BOOTSTRAP
   Every other module has registered its Kindling.onRoute
   handler by the time this runs (script order in index.html).
   ========================================================= */

// Single source of truth for the "Last updated" date shown on the
// legal pages (About/Privacy/Terms) - change this one line, not
// the separate page headers, when the pages are next revised.
window.Kindling.LEGAL_UPDATED = 'September 25, 2026';
document.querySelectorAll('[data-legal-updated]').forEach(el => {
    el.textContent = window.Kindling.LEGAL_UPDATED;
});

/*
 * The nav sits outside every .screen's own scroll container (each
 * .screen scrolls itself, not the window), so it never needs
 * repositioning - it only needs a background once content is
 * actually scrolled under it, so the transparent nav never slices
 * through the hero/page content. A capture-phase listener on
 * document catches scroll events from whichever .screen is
 * currently active without needing to re-bind on every route change.
 */
const navEl = document.querySelector('.nav');
document.addEventListener('scroll', () => {
    const active = document.querySelector('.screen.is-active');
    navEl.classList.toggle('is-scrolled', !!active && active.scrollTop > 4);
}, true);

window.Kindling.go();
