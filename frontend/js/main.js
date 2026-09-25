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

window.Kindling.go();
