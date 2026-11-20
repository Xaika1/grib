(function (G) {
  'use strict';

  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  const listeners = [];

  function effective() {
    const t = G.settings.theme();
    if (t === 'light' || t === 'dark') return t;
    return media && media.matches ? 'dark' : 'light';
  }

  function apply() {
    const theme = effective();
    document.documentElement.setAttribute('data-theme', theme);
    if (window.Chart) {
      const css = getComputedStyle(document.documentElement);
      Chart.defaults.locale = 'ru-RU';
      Chart.defaults.color = css.getPropertyValue('--muted').trim();
      Chart.defaults.borderColor = css.getPropertyValue('--border').trim();
      Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    }
    listeners.forEach((fn) => fn(theme));
  }

  if (media && media.addEventListener) media.addEventListener('change', apply);

  G.themes = {
    apply,
    effective,
    set(t) { G.settings.setTheme(t); apply(); },
    onChange(fn) { listeners.push(fn); return () => listeners.splice(listeners.indexOf(fn), 1); },
  };
})(window.G);
