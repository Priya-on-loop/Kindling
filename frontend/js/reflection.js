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

    function renderTimeline(items) {
        const journeyEl = $('#journey');
        const userMessages = items.filter(i => i.item_type === 'message' && i.detail === 'user');

        if (userMessages.length === 0) {
            journeyEl.innerHTML = '<li class="j-card">Nothing here yet. Your questions will build a timeline as you explore.</li>';
            return;
        }

        journeyEl.innerHTML = userMessages.map((item, i) => `
      <li class="j-card${i === userMessages.length - 1 ? ' is-now' : ''}">
        <time>${esc(formatWhen(item.timestamp))}</time>
        <span>${esc(item.data)}</span>
      </li>`).join('');
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

        const rows = K.patterns
            .map(p => ({ pattern: p, ms: totals[p.key] || 0 }))
            .filter(r => r.ms > 0)
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

    async function loadTimeline() {

        const journeyEl = $('#journey');
        const timeBarsEl = $('#timeBars');
        const sessionId = K.getSessionId();

        if (!sessionId) {
            journeyEl.innerHTML = '<li class="j-card">Start exploring on Explore to build your timeline.</li>';
            timeBarsEl.innerHTML = '<li class="time-bars-empty">Time you spend exploring will show up here.</li>';
            return;
        }

        try {

            const response = await fetch(`${K.API_BASE_URL}/api/dashboard/timeline/${sessionId}`);

            if (!response.ok) throw new Error(`Server returned ${response.status}`);

            const data = await response.json();
            const items = data.timeline || [];

            renderTimeline(items);
            renderTimeSpent(items);

        }

        catch (error) {
            console.error('Failed to load timeline:', error);
            journeyEl.innerHTML = '<li class="j-card">We could not reach the server. Please try again.</li>';
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

    K.onRoute.reflection = () => {
        loadTimeline();
        renderCalibration();
        requestAnimationFrame(() => $('#reflection').classList.add('is-shown'));
    };

})();
