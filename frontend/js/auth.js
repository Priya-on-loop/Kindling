/* =========================================================
   AUTH — real accounts
   POST /api/auth/signup and POST /api/auth/login are real
   backend endpoints (bcrypt-hashed passwords, a real users
   table). Additive: Explore/Inference/Career Graph never
   check auth state and keep working anonymously regardless.

   "Continue with Google" has no backend behind it (no OAuth
   integration exists) and stays an honest "coming soon."
   There's no forgot-password control in this build's markup,
   so there's nothing to wire for it.
   ========================================================= */

(() => {

    const K = window.Kindling;
    const { $, $$, toast } = K;

    let authMode = 'signin';
    const authForm = $('#authForm'), authErr = $('#authError'), aName = $('#aName');
    const authSubmit = $('#authSubmit'), aEmail = $('#aEmail'), aPass = $('#aPass');

    function setAuthMode(mode) {
        authMode = mode;
        $$('.auth-tabs [role=tab]').forEach(t => t.setAttribute('aria-selected', String(t.dataset.mode === mode)));
        $('[data-signup-only]').hidden = mode !== 'signup';
        authSubmit.textContent = mode === 'signup' ? 'Create account' : 'Sign in';
        aPass.autocomplete = mode === 'signup' ? 'new-password' : 'current-password';
        authErr.textContent = '';
    }

    $$('.auth-tabs [role=tab]').forEach(t => t.addEventListener('click', () => setAuthMode(t.dataset.mode)));
    $$('[data-auth-mode]').forEach(a => a.addEventListener('click', () => setAuthMode(a.dataset.authMode)));

    $('#pwToggle').addEventListener('click', e => {
        const show = aPass.type === 'password';
        aPass.type = show ? 'text' : 'password';
        e.target.textContent = show ? 'Hide' : 'Show';
    });

    function applySignedInUI() {

        const signedIn = K.isSignedIn();
        const email = K.getAuthEmail() || '';

        document.body.classList.toggle('signed-in', signedIn);

        const acctEmail = $('#acctEmail');
        if (acctEmail) acctEmail.textContent = signedIn ? email : '';

        const avatar = $('#navAvatar');
        if (!avatar) return;

        if (signedIn) {
            const initial = (email.trim()[0] || 'K').toUpperCase();
            avatar.textContent = initial;
            avatar.setAttribute('aria-label', `Settings, signed in as ${email}`);
        }
        else {
            avatar.innerHTML = '<svg width="12" height="12" aria-hidden="true"><use href="#spark"/></svg>';
            avatar.setAttribute('aria-label', 'Settings');
        }

    }

    K.applySignedInUI = applySignedInUI;

    authForm.addEventListener('submit', async e => {

        e.preventDefault();
        authErr.textContent = '';

        const email = aEmail.value.trim();
        const password = aPass.value;

        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            authErr.textContent = 'Enter a valid email address, like name@example.com.';
            aEmail.focus();
            return;
        }

        if (password.length < 8) {
            authErr.textContent = 'Passwords need at least 8 characters.';
            aPass.focus();
            return;
        }

        const endpoint = authMode === 'signup' ? '/api/auth/signup' : '/api/auth/login';

        authSubmit.disabled = true;
        const originalLabel = authSubmit.textContent;
        authSubmit.textContent = authMode === 'signup' ? 'Creating account…' : 'Signing in…';

        try {

            const response = await fetch(`${K.API_BASE_URL}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                authErr.textContent = data.detail || 'Something went wrong. Please try again.';
                return;
            }

            K.setAuth(data.token, data.email);
            applySignedInUI();

            authForm.reset();
            authErr.textContent = '';

            toast(authMode === 'signup' ? `Welcome to Kindling, ${data.email}` : `Welcome back, ${data.email}`);

            location.hash = 'explore';

        }

        catch (error) {
            console.error('Auth request failed:', error);
            authErr.textContent = "We couldn't reach the server. Please try again.";
        }

        finally {
            authSubmit.disabled = false;
            authSubmit.textContent = originalLabel;
        }

    });

    $('#googleBtn').addEventListener('click', () => {
        authErr.textContent = "Signing in with Google isn't available yet. No Google account is connected to Kindling.";
    });

    applySignedInUI();

})();
