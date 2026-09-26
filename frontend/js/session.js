/* =========================================================
   SESSION
   The one real identity concept in Kindling: an anonymous
   session id, exactly as backend/main.py and db.py define it
   (no accounts, no auth). "Save my exploration" in Settings
   controls whether this mirrors into localStorage (survives
   closing the tab) in addition to sessionStorage.
   ========================================================= */

(() => {

    const K = window.Kindling;

    K.API_BASE_URL = 'https://kindling-backend.onrender.com';

    const SESSION_KEY = 'kindling_session_id';
    const PERSIST_KEY = 'kindling_persist_session';

    K.getSessionId = function getSessionId() {

        try {

            let id = sessionStorage.getItem(SESSION_KEY);

            if (!id) {

                const persisted = localStorage.getItem(SESSION_KEY);

                if (persisted) {
                    id = persisted;
                    sessionStorage.setItem(SESSION_KEY, persisted);
                }

            }

            return id;

        }

        catch (error) {
            return null;
        }

    };

    K.setSessionId = function setSessionId(id) {

        try {

            sessionStorage.setItem(SESSION_KEY, id);

            if (localStorage.getItem(PERSIST_KEY) === 'true') {
                localStorage.setItem(SESSION_KEY, id);
            }

        }

        catch (error) {}

    };

    K.clearSession = function clearSession() {

        try {
            sessionStorage.removeItem(SESSION_KEY);
            localStorage.removeItem(SESSION_KEY);
        }

        catch (error) {}

    };

    K.isPersisting = function isPersisting() {

        try {
            return localStorage.getItem(PERSIST_KEY) === 'true';
        }

        catch (error) {
            return false;
        }

    };

    K.setPersisting = function setPersisting(on) {

        try {

            localStorage.setItem(PERSIST_KEY, on ? 'true' : 'false');

            if (on) {
                const current = sessionStorage.getItem(SESSION_KEY);
                if (current) localStorage.setItem(SESSION_KEY, current);
            }

            else {
                localStorage.removeItem(SESSION_KEY);
            }

        }

        catch (error) {}

    };


    /* =====================================================
       AUTH (real accounts, additive)
       The token here is literally the user's row id from
       POST /api/auth/signup or /api/auth/login — there's no
       expiry/refresh scheme, matching the same simplicity as
       kindling_session_id. Always in localStorage: signing in
       means "remember me," unlike the anonymous exploration
       session, which defaults to sessionStorage.
       ===================================================== */

    const AUTH_TOKEN_KEY = 'kindling_auth_token';
    const AUTH_EMAIL_KEY = 'kindling_auth_email';
    const AUTH_NAME_KEY = 'kindling_auth_name';

    K.getAuthToken = function getAuthToken() {
        try { return localStorage.getItem(AUTH_TOKEN_KEY); }
        catch (error) { return null; }
    };

    K.getAuthEmail = function getAuthEmail() {
        try { return localStorage.getItem(AUTH_EMAIL_KEY); }
        catch (error) { return null; }
    };

    // Real name if the account has one, otherwise the real email
    // local-part fallback the backend already computed and returned
    // at signup/login time - never blank, never invented here.
    K.getAuthName = function getAuthName() {
        try { return localStorage.getItem(AUTH_NAME_KEY) || K.getAuthEmail() || ''; }
        catch (error) { return ''; }
    };

    K.setAuth = function setAuth(token, email, name) {
        try {
            localStorage.setItem(AUTH_TOKEN_KEY, token);
            localStorage.setItem(AUTH_EMAIL_KEY, email);
            if (name) localStorage.setItem(AUTH_NAME_KEY, name);
        }
        catch (error) {}
    };

    K.clearAuth = function clearAuth() {
        try {
            localStorage.removeItem(AUTH_TOKEN_KEY);
            localStorage.removeItem(AUTH_EMAIL_KEY);
            localStorage.removeItem(AUTH_NAME_KEY);
        }
        catch (error) {}
    };

    K.isSignedIn = function isSignedIn() {
        return Boolean(K.getAuthToken());
    };

    /* =====================================================
       CONNECT THREADS
       Off by default: Inference, Career Graph, and Reflection each
       read one real thread's results (K.getResultsSessionId(), which
       defaults to the active Explore thread but can be switched
       independently via the scope bar below). On: those same three
       pages ask the backend for scope=all instead - the real combined
       result across every one of this account's real threads.
       Persisted like every other Settings toggle (localStorage only,
       no backend settings storage exists for any of them).
       ===================================================== */

    const CONNECT_THREADS_KEY = 'kindling_connect_threads';
    let resultsSessionId = null;

    K.isConnectThreadsOn = function isConnectThreadsOn() {
        try { return localStorage.getItem(CONNECT_THREADS_KEY) === 'true'; }
        catch (error) { return false; }
    };

    K.setConnectThreads = function setConnectThreads(on) {
        try { localStorage.setItem(CONNECT_THREADS_KEY, on ? 'true' : 'false'); }
        catch (error) {}
        window.dispatchEvent(new CustomEvent('kindling:scope-change'));
    };

    // The thread Inference/Career Graph/Reflection show in single
    // mode - independent of K.getSessionId() (Explore's own active
    // thread), so picking a different thread in the switcher doesn't
    // change what Explore is doing. Resets to "follow the active
    // thread" (null) on a fresh page load - not persisted, since
    // there's no real expectation this survives a reload the way the
    // Connect Threads toggle itself does.
    K.getResultsSessionId = function getResultsSessionId() {
        return resultsSessionId || K.getSessionId();
    };

    // No event dispatch here on purpose - the dropdown's own onChange
    // (below) already calls the caller's refetch directly, and the
    // internal "default to a real thread" correction in
    // renderScopeBar also uses this, which would otherwise re-enter
    // itself via the scope-change listener each page sets up.
    K.setResultsSessionId = function setResultsSessionId(id) {
        resultsSessionId = id;
    };

    K.fetchUserThreads = async function fetchUserThreads() {
        const token = K.getAuthToken();
        if (!token) return [];
        try {
            const response = await fetch(`${K.API_BASE_URL}/api/auth/sessions?token=${encodeURIComponent(token)}`);
            if (!response.ok) return [];
            const data = await response.json();
            return Array.isArray(data.sessions) ? data.sessions : [];
        }
        catch (error) {
            return [];
        }
    };

    /*
     * Shared "Showing: ..." bar for Inference/Career Graph/Reflection
     * - one implementation so the three pages can't drift out of sync
     * on what this looks like or how switching threads/scope behaves.
     * onChange fires after every real switch (thread or scope) so the
     * calling page can refetch its own data without a full reload.
     */
    K.renderScopeBar = async function renderScopeBar(container, onChange) {
        if (!container) return;

        const combined = K.isConnectThreadsOn();

        if (combined) {
            container.innerHTML = `<span class="scope-label">Showing: all conversations</span>`;
            return;
        }

        const threads = await K.fetchUserThreads();
        const activeId = K.getResultsSessionId();
        const active = threads.find(t => t.session_id === activeId) || threads[0];

        if (!active) {
            container.innerHTML = `<span class="scope-label">Showing: this conversation</span>`;
            return;
        }

        if (active.session_id !== activeId) K.setResultsSessionId(active.session_id);

        if (threads.length <= 1) {
            container.innerHTML = `<span class="scope-label">Showing: ${K.esc(active.label)}</span>`;
            return;
        }

        container.innerHTML = `
      <span class="scope-label">Showing:</span>
      <select class="scope-switcher" aria-label="Choose which thread to show">
        ${threads.map(t => `<option value="${t.session_id}"${t.session_id === active.session_id ? ' selected' : ''}>${K.esc(t.label)}</option>`).join('')}
      </select>`;

        container.querySelector('.scope-switcher').addEventListener('change', e => {
            K.setResultsSessionId(e.target.value);
            onChange?.();
        });
    };

})();
