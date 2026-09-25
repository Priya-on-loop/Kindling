/* =========================================================
   HASH ROUTER
   Kept exactly as built in the mockup.
   ========================================================= */

const Kindling = window.Kindling || {};
window.Kindling = Kindling;

Kindling.$ = (s, r = document) => r.querySelector(s);
Kindling.$$ = (s, r = document) => [...r.querySelectorAll(s)];

Kindling.onRoute = {};

Kindling.routes = ['home', 'explore', 'inference', 'graph', 'reflection', 'settings', 'auth', 'about', 'privacy', 'terms'];

/*
 * Explore, Inference, Career Graph, and Reflection require a real
 * signed-in account. Landing (#home), #settings, and #auth itself
 * stay open to everyone. Kindling.isSignedIn() is defined in
 * session.js, which loads before go() is ever actually called
 * (only invoked from main.js after every script has loaded, or
 * from a later hashchange event) — the reference here just isn't
 * resolved until then.
 */
Kindling.gatedRoutes = ['explore', 'inference', 'graph', 'reflection'];

Kindling.go = function go() {
    const page = Kindling.routes.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'home';

    if (Kindling.gatedRoutes.includes(page) && !Kindling.isSignedIn()) {
        // Covers both in-app navigation to a gated link and a
        // direct/bookmarked load straight into #explore etc. —
        // this reassigns location.hash, which fires 'hashchange'
        // and re-enters go() for #auth instead of rendering here.
        location.hash = 'auth';
        return;
    }

    document.body.dataset.page = page;
    Kindling.$$('.screen').forEach(s => s.classList.toggle('is-active', s.id === page));
    Kindling.$$('[data-route]').forEach(a => a.dataset.route === page ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
    Kindling.onRoute[page]?.();
};

addEventListener('hashchange', Kindling.go);
