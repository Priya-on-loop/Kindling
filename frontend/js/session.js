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

})();
