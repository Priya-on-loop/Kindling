/* =========================================================
   SHARED HELPERS + NODE DRAWING
   Used by inference.js and career-graph.js. Kept from the
   mockup: node size/glow are purely visual — no number is
   ever printed anywhere a node is drawn.
   ========================================================= */

(() => {

    const K = window.Kindling;
    const { $ } = K;
    const svgNS = 'http://www.w3.org/2000/svg';

    K.el = (tag, attrs = {}, parent) => {
        const n = document.createElementNS(svgNS, tag);
        for (const k in attrs) n.setAttribute(k, attrs[k]);
        if (parent) parent.appendChild(n);
        return n;
    };

    K.lc = s => s.split(' ').map(w => /^[A-Z]{2}/.test(w) ? w : w.toLowerCase()).join(' ');

    K.esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    K.toast = function toast(msg) {
        const t = $('#toast'); t.textContent = msg; t.classList.add('is-shown');
        clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('is-shown'), 2200);
    };

    K.colorOf = {
        warm: 'var(--warm)', cool: 'var(--cool)', pale: 'var(--cool-soft)', violet: 'var(--violet)',
        hub: 'var(--cool-soft)', area: 'var(--violet)', related: 'var(--warm-soft)', direction: 'var(--amber)',
        // Real Career Graph tree node types (backend/career_tree.py):
        // field reuses "related"'s cream tone, career reuses "direction"'s amber.
        field: 'var(--warm-soft)', career: 'var(--amber)'
    };

    K.addGlow = function addGlow(svg, dev = 6) {
        let defs = svg.querySelector('defs') || svg.insertBefore(K.el('defs'), svg.firstChild);
        const f = K.el('filter', { id: svg.id + '-glow', x: '-150%', y: '-150%', width: '400%', height: '400%' }, defs);
        K.el('feGaussianBlur', { stdDeviation: dev }, f);
        return `url(#${svg.id}-glow)`;
    };

    K.drawNode = function drawNode(parent, n, glow, { core = 4.5, halo = 14, label = n.label, lx, ly, anchor = 'start', cls = '' } = {}) {
        const g = K.el('g', { class: 'node ' + cls, tabindex: '0', role: 'button', 'aria-label': label, transform: `translate(${n.x} ${n.y})` }, parent);
        const c = K.colorOf[n.tone || n.type];
        K.el('circle', { r: Math.max(core + 12, 14), fill: 'transparent' }, g);
        K.el('circle', { class: 'halo', r: halo, fill: c, filter: glow }, g);
        K.el('circle', { class: 'ring', r: core + 6 }, g);
        K.el('circle', { r: core, fill: c }, g);
        K.el('circle', { r: core * 0.45, fill: '#fffaf0', opacity: 0.9 }, g);
        const t = K.el('text', { x: lx ?? core + 11, y: ly ?? 5, 'text-anchor': anchor }, g);
        t.textContent = label;
        return g;
    };

    K.onActivate = function onActivate(g, fn) {
        g.addEventListener('click', fn);
        g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(); } });
    };

})();
