/* UBVPROJECT — вкладки, тема, появление блоков, живой знак «карданов подвес». */

(function () {
  const root = document.documentElement;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  // тема
  try { const t = localStorage.getItem('ubv-theme'); if (t) root.dataset.theme = t; } catch (e) {}
  const isLight = () => root.dataset.theme ? root.dataset.theme === 'light' : matchMedia('(prefers-color-scheme: light)').matches;
  document.querySelectorAll('[data-act="theme"]').forEach(b => b.addEventListener('click', () => {
    const go = () => { root.dataset.theme = isLight() ? 'dark' : 'light'; try { localStorage.setItem('ubv-theme', root.dataset.theme); } catch (e) {} };
    document.startViewTransition && !reduce ? document.startViewTransition(go) : go();
  }));
  // вкладки
  const tabs = [...document.querySelectorAll('[data-tab-btn]')];
  const secs = [...document.querySelectorAll('main > section[data-tab]')];
  const ink = document.querySelector('.tabs .ink');
  function moveInk() {
    const cur = tabs.find(t => t.getAttribute('aria-current') === 'page');
    if (!ink || !cur || !cur.offsetParent) return;
    ink.style.left = cur.offsetLeft + 12 + 'px'; ink.style.width = cur.offsetWidth - 24 + 'px';
  }
  function show(id, push) {
    if (!secs.some(s => s.dataset.tab === id)) id = 'home';
    const go = () => {
      secs.forEach(s => s.classList.toggle('on', s.dataset.tab === id));
      tabs.forEach(t => t.toggleAttribute('aria-current', false));
      tabs.filter(t => t.dataset.tabBtn === (id === 'powered' ? 'projects' : id)).forEach(t => t.setAttribute('aria-current', 'page'));
      moveInk(); window.scrollTo({ top: 0, behavior: 'instant' }); armReveal(); armBars();
      document.dispatchEvent(new CustomEvent('ubv:tab', { detail: id }));
    };
    if (push) { try { history.replaceState(null, '', '#' + id); } catch (e) { location.hash = id; } }
    document.startViewTransition && !reduce && push ? document.startViewTransition(go) : go();
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-tab-btn],[data-go]'); if (!b) return;
    e.preventDefault(); show(b.dataset.tabBtn || b.dataset.go, true);
  });
  addEventListener('resize', moveInk);
  // появление при прокрутке: прячем только то, что ниже первого экрана
  let io;
  function armReveal() {
    if (reduce || !('IntersectionObserver' in window)) return;
    io && io.disconnect();
    io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { en.target.classList.remove('pre'); io.unobserve(en.target); } }), { rootMargin: '0px 0px -8% 0px' });
    document.querySelectorAll('main > section.on .reveal').forEach(el => {
      if (el.getBoundingClientRect().top > innerHeight * 0.92) { el.classList.add('pre'); io.observe(el); } else el.classList.remove('pre');
    });
  }
  function armBars() {
    document.querySelectorAll('main > section.on .opt').forEach(o => {
      if (reduce) return o.classList.remove('idle');
      o.classList.add('idle');
      const ob = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { setTimeout(() => o.classList.remove('idle'), 120); ob.disconnect(); } }), { threshold: .3 });
      ob.observe(o);
    });
  }
  // живой знак: три рамки подвеса, ортографическая проекция, видимое/невидимое
  window.UBVGimbal = function (svg, opts) {
    opts = Object.assign({ R: 80, tilt: 22, speed: 9, w: 6, hidden: true, hover: true }, opts || {});
    const NS = 'http://www.w3.org/2000/svg';
    const C = 100, N = 120;
    const rings = [[1, 0, 0], [0, 1, 0], [0, 0, 1]].map((n, k) => {
      const back = document.createElementNS(NS, 'path'), front = document.createElementNS(NS, 'path');
      back.setAttribute('fill', 'none'); front.setAttribute('fill', 'none');
      back.setAttribute('class', k === 1 ? 's-a' : 's-i'); front.setAttribute('class', k === 1 ? 's-a' : 's-i');
      back.setAttribute('stroke-width', opts.w * 0.3); back.setAttribute('stroke-dasharray', '3 5'); back.setAttribute('opacity', '.55');
      front.setAttribute('stroke-width', k === 1 ? opts.w * 1.1 : opts.w); front.setAttribute('stroke-linecap', 'round');
      if (!opts.hidden) back.style.display = 'none';
      svg.appendChild(back); svg.appendChild(front);
      return { n, back, front };
    });
    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('cx', C); dot.setAttribute('cy', C); dot.setAttribute('r', opts.w * 0.9); dot.setAttribute('class', 'f-i');
    svg.appendChild(dot);
    function basis(n) {
      const a = Math.abs(n[0]) < .9 ? [1, 0, 0] : [0, 1, 0];
      let e1 = [a[1] * n[2] - a[2] * n[1], a[2] * n[0] - a[0] * n[2], a[0] * n[1] - a[1] * n[0]];
      const L = Math.hypot(...e1); e1 = e1.map(v => v / L);
      const e2 = [n[1] * e1[2] - n[2] * e1[1], n[2] * e1[0] - n[0] * e1[2], n[0] * e1[1] - n[1] * e1[0]];
      return [e1, e2];
    }
    rings.forEach(r => r.basis = basis(r.n));
    let yaw = 20, tilt = opts.tilt, tx = 0, ty = 0, last = performance.now();
    function draw() {
      const cy = Math.cos(yaw * Math.PI / 180), sy = Math.sin(yaw * Math.PI / 180);
      const t = (tilt + ty) * Math.PI / 180, ct = Math.cos(t), st = Math.sin(t);
      rings.forEach(r => {
        let f = '', bk = '', pf = false, pb = false;
        for (let i = 0; i <= N; i++) {
          const u = 2 * Math.PI * i / N, [e1, e2] = r.basis;
          let x = Math.cos(u) * e1[0] + Math.sin(u) * e2[0], y = Math.cos(u) * e1[1] + Math.sin(u) * e2[1], z = Math.cos(u) * e1[2] + Math.sin(u) * e2[2];
          [x, z] = [x * cy + z * sy, -x * sy + z * cy];
          [y, z] = [y * ct - z * st, y * st + z * ct];
          const X = (C + x * opts.R).toFixed(1), Y = (C - y * opts.R).toFixed(1);
          if (z >= 0) { f += (pf ? 'L' : 'M') + X + ' ' + Y; pf = true; pb = false; }
          else { bk += (pb ? 'L' : 'M') + X + ' ' + Y; pb = true; pf = false; }
        }
        r.front.setAttribute('d', f); r.back.setAttribute('d', bk);
      });
    }
    function tick(now) {
      const dt = Math.min(64, now - last); last = now;
      yaw += opts.speed * dt / 1000 + tx * 0.02;
      draw();
      if (!reduce) requestAnimationFrame(tick);
    }
    if (opts.hover && !reduce) addEventListener('pointermove', e => { tx = (e.clientX / innerWidth - .5) * 2; ty = (e.clientY / innerHeight - .5) * -14; });
    draw(); if (!reduce) requestAnimationFrame(tick);
  };
  document.querySelectorAll('svg[data-gimbal]').forEach(s => UBVGimbal(s, JSON.parse(s.dataset.gimbal || '{}')));
  show((location.hash || '#home').slice(1), false);
  requestAnimationFrame(moveInk);
})();
