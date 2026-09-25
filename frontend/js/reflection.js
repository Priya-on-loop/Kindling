/* =========================================================
   REFLECTION — real timeline, time spent, + calibration
   Real endpoints: GET /api/dashboard/timeline/{session_id},
   reusing GET /api/chat/inference + POST /api/user/trait/decision
   for calibration (same data patterns.js already wired for
   Inference).

   "Time spent exploring" sums real node_time events (dwell time
   on a Career Graph node, tagged with that occupation's own real
   dominant RIASEC dimension — see career-graph.js) from the same
   timeline this page already fetches. Chat-thread time is
   deliberately not included: Phase 1 only scores the whole
   transcript once at the end, so there's no honest per-turn area
   to attribute live chat minutes to, and this page won't invent
   one. The exploration timeline below is real: each entry is one
   of your own real messages, in order, with its real timestamp.
   ========================================================= */

(() => {

    const K = window.Kindling;
    const { $, $$, esc } = K;

    function formatWhen(iso) {
        try {
            const d = new Date(iso);
            return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
        }
        catch (error) {
            return '';
        }
    }

    function formatDuration(ms) {
        const totalMinutes = Math.round(ms / 60000);
        const h = Math.floor(totalMinutes / 60);
        const m = totalMinutes % 60;
        return `${h}h ${String(m).padStart(2, '0')}m`;
    }

    /*
     * Real dwell time on Career Graph nodes, logged by
     * career-graph.js through the existing POST /api/events/log
     * endpoint as node_time events ({area, startedAt, endedAt}),
     * summed per area here. Chat-thread time isn't included: Phase 1
     * only scores the whole transcript once at the end, so there's
     * no honest per-turn area to attribute live chat minutes to.
     */
    function renderTimeSpent(items) {
        const timeBarsEl = $('#timeBars');

        const totals = {};
        items
            .filter(i => i.item_type === 'event' && i.detail === 'node_time')
            .forEach(i => {
                try {
                    const { area, startedAt, endedAt } = JSON.parse(i.data);
                    const ms = new Date(endedAt) - new Date(startedAt);
                    if (area && ms > 0) totals[area] = (totals[area] || 0) + ms;
                }
                catch (error) {}
            });

        /*
         * Filtering on r.ms > 0 alone let a real-but-tiny duration
         * (a few seconds) through, which formatDuration() then
         * rounds down to "0h 00m" — a row that looks broken instead
         * of informative. Hide anything that would display as zero.
         */
        const rows = K.patterns
            .map(p => ({ pattern: p, ms: totals[p.key] || 0 }))
            .filter(r => Math.round(r.ms / 60000) > 0)
            .sort((a, b) => b.ms - a.ms);

        if (rows.length === 0) {
            timeBarsEl.innerHTML = '<li class="time-bars-empty">Time you spend exploring will show up here.</li>';
            return;
        }

        /*
         * REAL BUG (found in testing): using rows[0].ms alone as the
         * scale meant a single short interaction was always its own
         * max, so ms/maxMs === 1 and the bar rendered 100% full
         * regardless of how small the real duration was (confirmed:
         * a genuine 6-second node_time event, not a near-zero/unit
         * bug, still produced fill_pct 100). Floor the scale at 60
         * real minutes so a few-second glance renders as the sliver
         * it actually is, and only real accumulated time fills the
         * bar meaningfully.
         */
        const SIXTY_MINUTES_MS = 60 * 60 * 1000;
        const maxMs = Math.max(rows[0].ms, SIXTY_MINUTES_MS);

        timeBarsEl.innerHTML = rows.map(r => `
      <li class="time-row" style="--fill-pct:${Math.round((r.ms / maxMs) * 100)}%">
        <span class="time-row-area">${esc(r.pattern.label)}</span>
        <span class="time-track"><span class="time-fill"></span></span>
        <span class="time-row-value">${esc(formatDuration(r.ms))}</span>
      </li>`).join('');

        // Two rAFs: one to let the 0%-width fills paint, one to then
        // flip the class that transitions them to their real width —
        // otherwise the browser can coalesce both into one frame and
        // the bars just appear full instead of animating in.
        requestAnimationFrame(() => requestAnimationFrame(() => {
            $$('.time-row', timeBarsEl).forEach(row => row.classList.add('is-in'));
        }));
    }

    async function loadTimeSpent() {

        const timeBarsEl = $('#timeBars');
        const sessionId = K.getSessionId();

        if (!sessionId) {
            timeBarsEl.innerHTML = '<li class="time-bars-empty">Time you spend exploring will show up here.</li>';
            return;
        }

        try {

            const response = await fetch(`${K.API_BASE_URL}/api/dashboard/timeline/${sessionId}`);

            if (!response.ok) throw new Error(`Server returned ${response.status}`);

            const data = await response.json();
            renderTimeSpent(data.timeline || []);

        }

        catch (error) {
            console.error('Failed to load time spent:', error);
            timeBarsEl.innerHTML = '<li class="time-bars-empty">We could not reach the server. Please try again.</li>';
        }

    }

    function renderCalibration() {

        const calEl = $('#calibration');

        calEl.innerHTML = K.patterns.map(t => {
            const c = K.colorOf[t.tone], v = K.feelings[t.id];
            return `<li class="cal-row"><span class="theme-tag"><i style="background:${c};box-shadow:0 0 6px ${c}"></i>${esc(t.label)}</span>
        <span class="cal-btns" role="group" aria-label="${esc(t.label)}">
          <button class="btn-line" data-cal="${t.id}" data-v="yes" aria-pressed="${v === 'yes'}">This fits</button>
          <button class="btn-line" data-cal="${t.id}" data-v="no" aria-pressed="${v === 'no'}">Not quite</button></span></li>`;
        }).join('');

    }

    $('#calibration').addEventListener('click', e => {
        const b = e.target.closest('[data-cal]');
        if (b) K.setFeeling(b.dataset.cal, b.dataset.v);
    });

    K.onFeelingChange.push(renderCalibration);

    /* =====================================================
       "YOUR TAKE" — real reflection notes
       POST /api/reflection/note (real strict-JSON-schema LLM
       extraction, resolved against the student's real current
       Career Graph and applied server-side), GET /api/reflection/
       notes, DELETE .../preference/{id} and .../note/{id}. Chips
       are the flat, live set of every active preference across
       every saved note; the list below is the raw notes with
       their own per-note delete.
       ===================================================== */

    const TAKE_KIND_PREFIX = {
        hide_field: 'Hiding',
        focus_field: 'Focusing on',
        pattern_adjust: "Doesn't fit",
        new_to_them: 'Discovered',
    };

    const takeInput = $('#takeInput'), takeCounter = $('#takeCounter'), takeSave = $('#takeSave'), takeForm = $('#takeForm');
    const takeChipsEl = $('#takeChips'), takeNotesEl = $('#takeNotes');

    function flattenChips(notes) {
        const chips = [];
        notes.forEach(note => (note.preferences || []).forEach(pref => chips.push(pref)));
        return chips;
    }

    function renderTakeChips(notes) {
        const chips = flattenChips(notes);
        if (!chips.length) { takeChipsEl.hidden = true; takeChipsEl.innerHTML = ''; return; }
        takeChipsEl.hidden = false;
        takeChipsEl.innerHTML = chips.map(c => `
      <span class="take-chip" data-pref-id="${c.id}">
        ${esc(TAKE_KIND_PREFIX[c.kind] || c.kind)}: ${esc(c.label)}
        <button type="button" aria-label="Undo ${esc(TAKE_KIND_PREFIX[c.kind] || c.kind)}: ${esc(c.label)}">
          <svg width="9" height="9" viewBox="0 0 9 9" aria-hidden="true"><path d="M1 1l7 7M8 1 1 8" stroke="currentColor" stroke-width="1.3"/></svg>
        </button>
      </span>`).join('');
    }

    function renderTakeNotes(notes) {
        if (!notes.length) {
            takeNotesEl.innerHTML = '<p class="take-notes-empty">Notes you save will show up here.</p>';
            return;
        }
        takeNotesEl.innerHTML = notes.map(n => `
      <div class="take-note-row" data-note-id="${n.id}">
        <div class="take-note-row-head">
          <p class="take-note-text">${esc(n.note_text)}</p>
          <span class="take-note-date">${esc(formatWhen(n.created_at))}</span>
        </div>
        <button type="button" class="take-note-delete" data-delete-note="${n.id}">Delete</button>
      </div>`).join('');
    }

    async function loadTakeNotes() {
        const token = K.getAuthToken();
        if (!token) { renderTakeChips([]); renderTakeNotes([]); return; }

        try {
            const response = await fetch(`${K.API_BASE_URL}/api/reflection/notes?token=${encodeURIComponent(token)}`);
            if (!response.ok) throw new Error(`Server returned ${response.status}`);
            const data = await response.json();
            const notes = data.notes || [];
            renderTakeChips(notes);
            renderTakeNotes(notes);
        }
        catch (error) {
            console.error('Failed to load reflection notes:', error);
        }
    }

    if (takeInput) {
        takeInput.addEventListener('input', () => {
            const len = takeInput.value.length;
            takeCounter.textContent = `${len}/1000`;
            takeCounter.classList.toggle('is-near-limit', len > 900);
            takeSave.disabled = !takeInput.value.trim();
        });

        takeForm.addEventListener('submit', async e => {
            e.preventDefault();
            const noteText = takeInput.value.trim();
            if (!noteText) return;

            const token = K.getAuthToken();
            const sessionId = K.getSessionId();
            if (!token) { K.toast('Sign in to save your take.'); return; }
            if (!sessionId) { K.toast("Start exploring first. There's nothing to reflect on yet."); return; }

            takeSave.disabled = true;
            const originalLabel = takeSave.textContent;
            takeSave.textContent = 'Saving…';

            try {
                const response = await fetch(`${K.API_BASE_URL}/api/reflection/note`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token, session_id: sessionId, note_text: noteText })
                });
                if (!response.ok) throw new Error(`Server returned ${response.status}`);

                takeInput.value = '';
                takeCounter.textContent = '0/1000';
                await loadTakeNotes();
                K.toast('Noted. Kindling adjusted what it shows you.');
            }
            catch (error) {
                console.error('Failed to save reflection note:', error);
                K.toast("We couldn't save that. Please try again.");
            }
            finally {
                takeSave.textContent = originalLabel;
                takeSave.disabled = !takeInput.value.trim();
            }
        });

        takeChipsEl.addEventListener('click', async e => {
            const chipEl = e.target.closest('.take-chip');
            if (!chipEl) return;
            const token = K.getAuthToken();
            if (!token) return;

            try {
                const response = await fetch(`${K.API_BASE_URL}/api/reflection/preference/${chipEl.dataset.prefId}?token=${encodeURIComponent(token)}`, { method: 'DELETE' });
                if (!response.ok) throw new Error(`Server returned ${response.status}`);
                await loadTakeNotes();
                K.toast('Undone.');
            }
            catch (error) {
                console.error('Failed to undo preference:', error);
                K.toast("We couldn't undo that. Please try again.");
            }
        });

        takeNotesEl.addEventListener('click', async e => {
            const btn = e.target.closest('[data-delete-note]');
            if (!btn) return;
            const token = K.getAuthToken();
            if (!token) return;

            try {
                const response = await fetch(`${K.API_BASE_URL}/api/reflection/note/${btn.dataset.deleteNote}?token=${encodeURIComponent(token)}`, { method: 'DELETE' });
                if (!response.ok) throw new Error(`Server returned ${response.status}`);
                await loadTakeNotes();
                K.toast('Note deleted.');
            }
            catch (error) {
                console.error('Failed to delete note:', error);
                K.toast("We couldn't delete that. Please try again.");
            }
        });
    }

    K.onRoute.reflection = () => {
        loadTimeSpent();
        renderCalibration();
        loadTakeNotes();
        requestAnimationFrame(() => $('#reflection').classList.add('is-shown'));
    };

})();
