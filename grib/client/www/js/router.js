(function (G) {
  'use strict';

  const routes = [];
  let cleanup = null;
  let renderSeq = 0;

  function compile(pattern) {
    const keys = [];
    const re = new RegExp('^' + pattern.replace(/:([a-zA-Z]+)/g, (_, k) => { keys.push(k); return '([^/]+)'; }) + '/?$');
    return { re, keys };
  }

  G.router = {
    add(pattern, view, opts) {
      const c = compile(pattern);
      routes.push(Object.assign({ pattern, view, re: c.re, keys: c.keys }, opts || {}));
    },
    current() { return location.hash.replace(/^#/, '') || '/'; },
    go(path) { if (location.hash !== '#' + path) location.hash = '#' + path; else this.resolve(); },
    async resolve() {
      const path = this.current();
      let route = null;
      let params = {};
      for (const r of routes) {
        const m = r.re.exec(path);
        if (m) {
          route = r;
          r.keys.forEach((k, i) => { params[k] = decodeURIComponent(m[i + 1]); });
          break;
        }
      }
      if (!route) { this.go('/projects'); return; }
      if (!route.public && !G.api.token()) { this.go('/login'); return; }

      if (typeof cleanup === 'function') { try { cleanup(); } catch (e) { console.error(e); } }
      cleanup = null;
      const seq = ++renderSeq;
      const el = G.app.mount(route, params);
      try {
        const result = await route.view(el, params);
        if (seq === renderSeq) cleanup = result; else if (typeof result === 'function') result();
      } catch (e) {
        if (seq !== renderSeq) return;
        console.error(e);
        G.clear(el).appendChild(G.errorBox(e));
      }
    },
    isStale(seq) { return seq !== renderSeq; },
    start() {
      window.addEventListener('hashchange', () => this.resolve());
      this.resolve();
    },
  };
})(window.G);
