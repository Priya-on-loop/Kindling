/* =========================================================
   SETTINGS
   Every control here does something real:
   - Appearance/text size: applied live, persisted to
     localStorage (kindling_theme / kindling_text_size).
   - Still background: toggles the real starfield animation.
   - Always show graph labels: toggles a real CSS class read
     by screens.css (#graphMap.labels-all).
   - Save my exploration: controls whether the real session id
     mirrors into localStorage (session.js), so it survives
     closing the tab.
   - Reset: really clears the session id both places.
   - Account: real sign-out, clearing the real auth token set by
     auth.js against POST /api/auth/signup|login.
   ========================================================= */

(() => {

    const K = window.Kindling;
    const { $, $$, toast } = K;

    /* ---- settings tabs ---- */
    const tabs = $$('.settings-nav [role=tab]');
    function showTab(tab) {
        tabs.forEach(t => {
            const on = t === tab;
            t.setAttribute('aria-selected', on);
            t.tabIndex = on ? 0 : -1;
            $('#' + t.getAttribute('aria-controls')).classList.toggle('is-active', on);
        });
    }
    tabs.forEach((t, i) => {
        t.tabIndex = i === 0 ? 0 : -1;
        t.addEventListener('click', () => showTab(t));
        t.addEventListener('keydown', e => {
            const d = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
            if (!d) return;
            e.preventDefault();
            const n = tabs[(i + d + tabs.length) % tabs.length];
            showTab(n); n.focus();
        });
    });

    /* ---- appearance ---- */
    const mq = matchMedia('(prefers-color-scheme: light)');
    let themeChoice = 'dark';
    try {
        const stored = localStorage.getItem('kindling_theme');
        themeChoice = stored === 'light' || stored === 'dark' ? stored : 'system';
    }
    catch (error) {}

    const bulb = $('#bulb');

    function applyTheme() {
        const resolved = themeChoice === 'system' ? (mq.matches ? 'light' : 'dark') : themeChoice;
        document.documentElement.dataset.theme = resolved;
        try {
            if (themeChoice === 'system') localStorage.removeItem('kindling_theme');
            else localStorage.setItem('kindling_theme', themeChoice);
        } catch (error) {}
        $$('#themeGroup [role=radio]').forEach(b => b.setAttribute('aria-checked', String(b.dataset.themeChoice === themeChoice)));
        bulb.setAttribute('aria-pressed', String(resolved === 'light'));
        bulb.setAttribute('aria-label', resolved === 'light' ? 'Turn on dark theme' : 'Turn on light theme');
    }
    bulb.addEventListener('click', () => { themeChoice = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'; applyTheme(); });
    $$('#themeGroup [role=radio]').forEach(b => b.addEventListener('click', () => { themeChoice = b.dataset.themeChoice; applyTheme(); }));
    mq.addEventListener?.('change', () => { if (themeChoice === 'system') applyTheme(); });
    applyTheme();

    let textChoice = 'default';
    try { textChoice = localStorage.getItem('kindling_text_size') === 'large' ? 'large' : 'default'; } catch (error) {}
    function applyText() {
        document.documentElement.dataset.text = textChoice === 'large' ? 'large' : '';
        try {
            if (textChoice === 'large') localStorage.setItem('kindling_text_size', 'large');
            else localStorage.removeItem('kindling_text_size');
        } catch (error) {}
        $$('#textGroup [role=radio]').forEach(b => b.setAttribute('aria-checked', String(b.dataset.textChoice === textChoice)));
    }
    $$('#textGroup [role=radio]').forEach(b => b.addEventListener('click', () => { textChoice = b.dataset.textChoice; applyText(); }));
    applyText();

    /* ---- toggles ---- */
    const toggle = (btn, initial, fn) => {
        if (!btn) return;
        btn.setAttribute('aria-checked', initial ? 'true' : 'false');
        btn.addEventListener('click', () => {
            const on = btn.getAttribute('aria-checked') !== 'true';
            btn.setAttribute('aria-checked', String(on));
            fn(on);
        });
    };

    toggle($('#saveSwitch'), K.isPersisting(), on => {
        K.setPersisting(on);
        toast(on ? 'Your session will be kept on this device' : 'Your session will clear when you close this tab');
    });

    toggle($('#stillSwitch'), false, on => {
        K.stillBackground = on;
        K.startSky();
    });

    toggle($('#labelsSwitch'), false, on => {
        $('#graphMap').classList.toggle('labels-all', on);
    });

    /* ---- reset ---- */
    $('#resetBtn').addEventListener('click', () => $('#resetDialog').showModal());
    $$('dialog [data-close]').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));
    $('#resetConfirm').addEventListener('click', () => {
        $('#resetDialog').close();
        K.clearSession();
        toast('Exploration reset');
        location.hash = 'home';
        location.reload();
    });

    /* ---- account ---- */
    /* #acctEmail and the nav avatar are kept in sync by
       auth.js's applySignedInUI(), called at load and after
       every sign-in/out — nothing to duplicate here. */

    $('#signOutBtn')?.addEventListener('click', () => {
        K.clearAuth();
        /*
         * Signing out must also end the exploration session —
         * otherwise the previous Explore conversation, Inference
         * results, and Career Graph (all keyed off
         * kindling_session_id, entirely independent of the auth
         * token) would still belong to whoever just signed out.
         * A reload is required, not optional: explore.js guards
         * its fetch/restore with a module-scoped `started` flag
         * that only resets on an actual reload, so clearing
         * storage alone wouldn't make a revisit to #explore
         * re-check anything (same reason /#resetConfirm below
         * reloads too).
         */
        K.clearSession();
        toast('Signed out');
        location.hash = 'home';
        location.reload();
    });

})();
