/* =========================================================
   STARFIELD — slow drift + occasional meteors
   Kept exactly as built in the mockup. Respects
   prefers-reduced-motion and the Settings "Still background"
   toggle (Kindling.stillBackground, set in settings.js).
   ========================================================= */

(() => {

    const sky = document.getElementById('sky');
    const ctx = sky.getContext('2d');
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

    let stars = [], meteors = [], raf, last = 0, nextMeteor = 3000;

    window.Kindling = window.Kindling || {};
    window.Kindling.stillBackground = false;

    function seedStars() {
        const dpr = Math.min(devicePixelRatio || 1, 2);
        sky.width = innerWidth * dpr; sky.height = innerHeight * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        stars = Array.from({ length: Math.round(innerWidth * innerHeight / 5200) }, () => {
            const warm = Math.random() < 0.12, cool = Math.random() < 0.35;
            const big = Math.random() >= 0.94;
            const r = big ? Math.random() * 0.8 + 1.1 : Math.random() * 0.8 + 0.25;
            const ang = Math.random() * Math.PI * 2, speed = (0.004 + Math.random() * 0.01) * (0.6 + r * 0.5);
            return {
                x: Math.random() * innerWidth, y: Math.random() * innerHeight, r,
                vx: Math.cos(ang) * speed, vy: Math.sin(ang) * speed,
                a: Math.random() * 0.5 + 0.15,
                c: warm ? '247,227,181' : cool ? '207,232,255' : '242,237,227',
                tw: Math.random() < 0.18 ? Math.random() * 0.0015 + 0.0005 : 0,
                ph: Math.random() * Math.PI * 2
            };
        });
        meteors = [];
    }

    function spawnMeteor() {
        const fromLeft = Math.random() < 0.5;
        const ang = (fromLeft ? 0.25 : Math.PI - 0.25) + (Math.random() - 0.5) * 0.5;
        meteors.push({
            x: fromLeft ? Math.random() * innerWidth * 0.6 : innerWidth * (0.4 + Math.random() * 0.6),
            y: Math.random() * innerHeight * 0.45,
            vx: Math.cos(ang) * 0.55, vy: Math.sin(ang) * 0.55,
            len: 110 + Math.random() * 120, life: 0, max: 1100 + Math.random() * 700,
            c: Math.random() < 0.4 ? '247,227,181' : '207,232,255'
        });
    }

    function drawSky(t = 0, dt = 0) {
        ctx.clearRect(0, 0, innerWidth, innerHeight);
        const W = innerWidth, H = innerHeight;
        for (const s of stars) {
            if (dt) {
                s.x += s.vx * dt; s.y += s.vy * dt;
                if (s.x < -4) s.x += W + 8; else if (s.x > W + 4) s.x -= W + 8;
                if (s.y < -4) s.y += H + 8; else if (s.y > H + 4) s.y -= H + 8;
            }
            const a = s.tw && dt ? s.a * (0.55 + 0.45 * Math.sin(t * s.tw + s.ph)) : s.a;
            ctx.fillStyle = `rgba(${s.c},${a})`;
            ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2); ctx.fill();
            if (s.r > 1.2) { ctx.fillStyle = `rgba(${s.c},${a * 0.12})`; ctx.beginPath(); ctx.arc(s.x, s.y, s.r * 4, 0, Math.PI * 2); ctx.fill(); }
        }
        if (!dt) return;
        nextMeteor -= dt;
        if (nextMeteor <= 0) { spawnMeteor(); nextMeteor = 4500 + Math.random() * 6000; }
        meteors = meteors.filter(m => {
            m.life += dt; m.x += m.vx * dt; m.y += m.vy * dt;
            const p = m.life / m.max; if (p >= 1) return false;
            const fade = Math.sin(p * Math.PI);
            const sp = Math.hypot(m.vx, m.vy);
            const tx = m.x - (m.vx / sp) * m.len, ty = m.y - (m.vy / sp) * m.len;
            const g = ctx.createLinearGradient(tx, ty, m.x, m.y);
            g.addColorStop(0, `rgba(${m.c},0)`); g.addColorStop(1, `rgba(${m.c},${0.75 * fade})`);
            ctx.strokeStyle = g; ctx.lineWidth = 1.2; ctx.lineCap = 'round';
            ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(m.x, m.y); ctx.stroke();
            ctx.fillStyle = `rgba(255,250,240,${0.9 * fade})`;
            ctx.beginPath(); ctx.arc(m.x, m.y, 1.3, 0, Math.PI * 2); ctx.fill();
            return true;
        });
    }

    function loop(t) {
        const dt = last ? Math.min(t - last, 50) : 16; last = t;
        if (!document.hidden) drawSky(t, dt);
        raf = requestAnimationFrame(loop);
    }

    function startSky() {
        cancelAnimationFrame(raf); last = 0;
        if (window.Kindling.stillBackground || reducedMotion.matches) drawSky();
        else raf = requestAnimationFrame(loop);
    }

    window.Kindling.startSky = startSky;

    seedStars(); startSky();

    let rs;
    addEventListener('resize', () => { clearTimeout(rs); rs = setTimeout(() => { seedStars(); startSky(); }, 150); });

})();
