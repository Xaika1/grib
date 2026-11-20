(function (G) {
  'use strict';

  G.settings = {
    sameOrigin: /^https?:$/.test(location.protocol) && !window.Capacitor && !window.gribDesktop,

    serverUrl() {
      const saved = G.storage.get('server', '');
      if (saved) return saved.replace(/\/+$/, '');
      if (this.sameOrigin) return location.origin;
      return 'http://localhost:8000';
    },
    setServerUrl(url) {
      const v = (url || '').trim().replace(/\/+$/, '');
      if (v) G.storage.set('server', v); else G.storage.remove('server');
    },
    theme() { return G.storage.get('theme', 'system'); },
    setTheme(t) { G.storage.set('theme', t); },
  };
})(window.G);
