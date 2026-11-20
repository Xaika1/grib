(function (G) {
  'use strict';
  const h = G.h;

  G.views.dashboard = async function (el, params) {
    const did = +params.did;
    let dash = await G.api.get('/dashboards/' + did);
    G.app.setProject(dash.project_id);
    const canEdit = G.can(dash.project_id, 'dashboard.edit');
    let range = G.storage.get('range.' + did, dash.default_range);
    const panels = new Map();
    let timer = null;
    let destroyed = false;

    const period = () => { const to = Date.now(); return { from: to - G.rangeMs(range), to }; };

    const liveDot = h('span', { class: 'live-dot' + (G.ws.online() ? ' on' : ''), title: 'Живые обновления' });
    const rangeSel = G.select(G.RANGES, range);
    rangeSel.addEventListener('change', () => { range = rangeSel.value; G.storage.set('range.' + did, range); loadAll(); });
    const refreshBtn = h('button', { class: 'btn icon', title: 'Обновить', onclick: () => loadAll() }, '↻');

    el.appendChild(h('div', { class: 'page-head' },
      h('div', { class: 'grow', style: { minWidth: '200px' } },
        h('div', { class: 'sub' }, h('a', { href: '#/p/' + dash.project_id + '/dashboards' }, '← Дашборды проекта')),
        h('h1', null, dash.title),
        dash.description ? h('div', { class: 'sub' }, dash.description) : null),
      h('div', { class: 'dash-toolbar' },
        liveDot, rangeSel, refreshBtn,
        canEdit ? h('a', { class: 'btn primary', href: '#/d/' + did + '/panel/new' }, '+ Панель') : null,
        h('button', { class: 'btn', onclick: () => G.exportDashboard(did).catch((e) => G.toast(G.errMsg(e), 'error')) }, 'Экспорт'),
        canEdit ? h('button', {
          class: 'btn icon', title: 'Настройки дашборда', onclick: async () => {
            const res = await G.dashboardDialog(dash.project_id, dash);
            if (res) G.router.resolve();
          },
        }, '⚙') : null)));

    const grid = h('div', { class: 'panel-grid' });
    el.appendChild(grid);

    if (!dash.panels.length) {
      el.removeChild(grid);
      el.appendChild(G.empty('На дашборде пока нет панелей.', canEdit ? h('a', { class: 'btn primary', href: '#/d/' + did + '/panel/new' }, 'Добавить панель') : null));
    }

    async function move(panelId, delta) {
      const ids = dash.panels.map((p) => p.id);
      const i = ids.indexOf(panelId);
      const j = i + delta;
      if (i < 0 || j < 0 || j >= ids.length) return;
      ids.splice(j, 0, ids.splice(i, 1)[0]);
      dash = await G.api.put('/dashboards/' + did + '/order', { panel_ids: ids });
      G.router.resolve();
    }

    dash.panels.forEach((p, idx) => {
      const body = h('div', { class: 'panel-body' });
      const tools = canEdit ? h('div', { class: 'tools' },
        idx > 0 ? h('button', { class: 'btn ghost sm icon', title: 'Левее', onclick: () => move(p.id, -1) }, '←') : null,
        idx < dash.panels.length - 1 ? h('button', { class: 'btn ghost sm icon', title: 'Правее', onclick: () => move(p.id, 1) }, '→') : null,
        h('a', { class: 'btn ghost sm icon', title: 'Изменить', href: '#/d/' + did + '/panel/' + p.id }, '✎'),
        h('button', {
          class: 'btn ghost sm icon', title: 'Удалить', onclick: async () => {
            if (!(await G.confirm('Удалить панель «' + (p.title || 'без названия') + '»?', { danger: true, ok: 'Удалить' }))) return;
            await G.api.del('/panels/' + p.id);
            G.router.resolve();
          },
        }, '✕')) : null;
      const card = h('div', { class: 'card panel', style: { gridColumn: 'span ' + p.grid_w, gridRow: 'span ' + p.grid_h } },
        h('div', { class: 'panel-head' }, h('h3', { title: p.title }, p.title || 'Без названия'),
          p.mode === 'collector' ? h('span', { class: 'badge', title: 'Данные сборщика, обновляются в реальном времени' }, 'сборщик') : null, tools),
        body);
      grid.appendChild(card);
      const view = G.panels.create(body, p, period);
      panels.set(p.id, { panel: p, view, card });
    });

    async function loadPanel(entry) {
      const pr = period();
      entry.view.loading();
      try {
        const data = await G.api.get('/panels/' + entry.panel.id + '/data?from_ms=' + pr.from + '&to_ms=' + pr.to);
        if (!destroyed) entry.view.update(data);
      } catch (e) {
        if (!destroyed) entry.view.showError(e);
      }
    }

    function loadAll(onlyLive) {
      panels.forEach((entry) => { if (!onlyLive || entry.panel.mode === 'live') loadPanel(entry); });
    }

    loadAll();
    if (dash.refresh_sec > 0) timer = setInterval(() => { if (!document.hidden) loadAll(true); }, dash.refresh_sec * 1000);

    G.ws.subscribe(did);
    const offSample = G.ws.on('sample', (msg) => {
      const pr = period();
      panels.forEach((entry) => {
        if (entry.panel.mode === 'collector' && entry.panel.collector_id === msg.collector_id) entry.view.append(msg.ts, msg.values, pr.from);
      });
    });
    const offStatus = G.ws.on('status', (s) => liveDot.classList.toggle('on', s.online));
    const offTheme = G.themes.onChange(() => panels.forEach((entry) => { entry.view.destroy(); loadPanel(entry); }));

    return () => {
      destroyed = true;
      clearInterval(timer);
      offSample();
      offStatus();
      offTheme();
      G.ws.unsubscribe();
      panels.forEach((entry) => entry.view.destroy());
    };
  };
})(window.G);
