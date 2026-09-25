/* =========================================================
   HASH ROUTER
   Kept exactly as built in the mockup.
   ========================================================= */

const Kindling = window.Kindling || {};
window.Kindling = Kindling;

Kindling.$ = (s, r = document) => r.querySelector(s);
Kindling.$$ = (s, r = document) => [...r.querySelectorAll(s)];

Kindling.onRoute = {};

/*
 * One source of truth for access: two lists, nothing else decides
 * whether a route needs a real account. Public: reachable by anyone.
 * Private: real account required (an account is required to explore
 * Kindling at all, so this is everything except the marketing/legal
 * pages and the auth screen itself).
 */
Kindling.publicRoutes = ['home', 'about', 'privacy', 'terms', 'auth'];
Kindling.privateRoutes = ['explore', 'inference', 'graph', 'reflection', 'settings'];
Kindling.routes = [...Kindling.publicRoutes, ...Kindling.privateRoutes];

// Kept as an alias in case anything else still reads the old name.
Kindling.gatedRoutes = Kindling.privateRoutes;

// Where a signed-out visitor was actually trying to go, so auth.js
// can send them there after a real login/signup instead of always
// dropping them on #explore.
const REDIRECT_KEY = 'kindling_redirect_after_login';

Kindling.go = function go() {
    // A route can carry one sub-path segment (currently only
    // #auth/login and #auth/signup) - the base segment is what
    // gates/screens/nav-highlighting key off; the sub segment is
    // handed to that route's own onRoute handler to interpret.
    const [rawPage, sub] = location.hash.slice(1).split('/');
    const page = Kindling.routes.includes(rawPage) ? rawPage : 'home';

    if (Kindling.privateRoutes.includes(page) && !Kindling.isSignedIn()) {
        // Covers both in-app navigation to a private link and a
        // direct/bookmarked load straight into #explore etc. —
        // remember the real destination, then reassign
        // location.hash, which fires 'hashchange' and re-enters
        // go() for #auth/login instead of rendering here.
        try { sessionStorage.setItem(REDIRECT_KEY, location.hash.slice(1)); } catch (error) {}
        location.hash = 'auth/login';
        return;
    }

    document.body.dataset.page = page;
    Kindling.$$('.screen').forEach(s => s.classList.toggle('is-active', s.id === page));
    Kindling.$$('[data-route]').forEach(a => a.dataset.route === page ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
    Kindling.onRoute[page]?.(sub);
};

addEventListener('hashchange', Kindling.go);
