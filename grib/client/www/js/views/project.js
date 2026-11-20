(function (G) {
  'use strict';
  const h = G.h;

  const TABS = [
    { key: 'dashboards', label: 'Дашборды', perm: 'dashboard.view' },
    { key: 'sources', label: 'Источники', perm: 'source.view' },
    { key: 'collectors', label: 'Сборщики', perm: 'collector.view' },
    { key: 'alerts', label: 'Алерты', perm: 'alert.view' },
    { key: 'members', label: 'Участники', perm: null },
    { key: 'settings', label: 'Проект', perm: 'project.manage' },
  ];
  G.PROJECT_TABS = TABS;

  G.projectPage = async function (el, pid, active) {
    G.app.setProject(pid);
    const project = await G.api.get('/projects/' + pid);
    const can = (p) => !p || project.permissions.indexOf(p) !== -1;
    el.appendChild(h('div', { class: 'page-head' },
      h('div', null, h('h1', null, project.name), h('div', { class: 'sub' }, 'Ваша роль: ' + (project.role || '—')))));
    el.appendChild(h('nav', { class: 'tabs' }, TABS.filter((t) => can(t.perm)).map((t) =>
      h('a', { href: '#/p/' + pid + '/' + t.key, class: t.key === active ? 'active' : '' }, t.label))));
    const body = h('div');
    el.appendChild(body);
    project.can = can;
    return { project, body };
  };

  function dashboardDialog(pid, dash) {
    const title = h('input', { required: true, value: dash ? dash.title : '' });
    const description = h('textarea', { rows: 2, value: dash ? dash.description : '' });
    const range = G.select(G.RANGES, dash ? dash.default_range : '6h');
    const refresh = G.select([
      { value: 0, label: 'выключено' }, { value: 10, label: '10 с' }, { value: 30, label: '30 с' },
      { value: 60, label: '1 мин' }, { value: 300, label: '5 мин' },
    ], dash ? dash.refresh_sec : 30);
    return new Promise((resolve) => {
      G.modal({
        title: dash ? 'Настройки дашборда' : 'Новый дашборд',
        body: h('div', { class: 'stack' }, G.field('Название', title), G.field('Описание', description),
          h('div', { class: 'grid2' }, G.field('Период по умолчанию', range), G.field('Обновление прямых запросов', refresh))),
        onClose: () => resolve(null),
        actions: [
          { label: 'Отмена' },
          {
            label: dash ? 'Сохранить' : 'Создать', kind: 'primary', submit: true,
            onClick: async () => {
              const body = { title: title.value.trim(), description: description.value, default_range: range.value, refresh_sec: +refresh.value };
              const res = dash ? await G.api.patch('/dashboards/' + dash.id, body) : await G.api.post('/projects/' + pid + '/dashboards', body);
              resolve(res);
            },
          },
        ],
      });
    });
  }
  G.dashboardDialog = dashboardDialog;

  G.exportDashboard = async function (id) {
    const data = await G.api.get('/dashboards/' + id + '/export');
    const name = (data.dashboard.title || 'dashboard').replace(/[^\wа-яё -]+/gi, '').trim().replace(/\s+/g, '_');
    G.download(name + '.grib.json', JSON.stringify(data, null, 2));
  };

  async function importDashboard(pid) {
    const text = await G.pickFile('.json,application/json');
    if (!text) return;
    let data;
    try { data = JSON.parse(text); } catch (e) { G.toast('Файл не является JSON', 'error'); return; }

    const send = async (sourceMap, collectorMap) => {
      try {
        const dash = await G.api.post('/projects/' + pid + '/dashboards/import', { data, source_map: sourceMap || {}, collector_map: collectorMap || {} });
        G.toast('Дашборд «' + dash.title + '» импортирован', 'ok');
        G.router.go('/d/' + dash.id);
      } catch (e) {
        if (e.status !== 409) { G.toast(G.errMsg(e), 'error'); return; }
        const missingS = e.data.missing_sources || [];
        const missingC = e.data.missing_collectors || [];
        const [sources, collectors] = await Promise.all([
          missingS.length ? G.api.get('/projects/' + pid + '/source-names') : [],
          missingC.length ? G.api.get('/projects/' + pid + '/collectors') : [],
        ]);
        const selects = {};
        const rows = [];
        missingS.forEach((n) => { selects['s:' + n] = G.select(sources.map((s) => ({ value: s.id, label: s.name + ' (' + s.type + ')' }))); rows.push(G.field('Источник «' + n + '» →', selects['s:' + n])); });
        missingC.forEach((n) => { selects['c:' + n] = G.select(collectors.map((c) => ({ value: c.id, label: c.name }))); rows.push(G.field('Сборщик «' + n + '» →', selects['c:' + n])); });
        if ((missingS.length && !sources.length) || (missingC.length && !collectors.length)) {
          G.toast('В проекте нет подходящих источников или сборщиков. Сначала создайте их.', 'error');
          return;
        }
        G.modal({
          title: 'Сопоставление источников',
          body: h('div', { class: 'stack' }, h('div', { class: 'muted' }, 'В файле дашборда источники указаны только по имени. Выберите, чем их заменить в этом проекте.'), rows),
          actions: [
            { label: 'Отмена' },
            {
              label: 'Импортировать', kind: 'primary', submit: true,
              onClick: () => {
                const sm = {}, cm = {};
                missingS.forEach((n) => { sm[n] = +selects['s:' + n].value; });
                missingC.forEach((n) => { cm[n] = +selects['c:' + n].value; });
                send(Object.assign({}, sourceMap, sm), Object.assign({}, collectorMap, cm));
              },
            },
          ],
        });
      }
    };
    send();
  }

  G.views.projectDashboards = async function (el, params) {
    const pid = +params.pid;
    const { project, body } = await G.projectPage(el, pid, 'dashboards');
    const canEdit = project.can('dashboard.edit');
    body.appendChild(h('div', { class: 'row', style: { marginBottom: '14px' } },
      canEdit ? h('button', { class: 'btn primary', onclick: async () => { const d = await dashboardDialog(pid); if (d) G.router.go('/d/' + d.id); } }, '+ Дашборд') : null,
      canEdit ? h('button', { class: 'btn', onclick: () => importDashboard(pid) }, 'Импорт из JSON') : null));
    const list = h('div', null, G.loading());
    body.appendChild(list);
    const dashboards = await G.api.get('/projects/' + pid + '/dashboards');
    G.clear(list);
    if (!dashboards.length) {
      list.appendChild(G.empty('В проекте пока нет дашбордов.' + (canEdit && !project.counts.sources ? ' Начните с подключения источника данных.' : ''),
        canEdit && !project.counts.sources && project.can('source.manage') ? h('a', { class: 'btn primary', href: '#/p/' + pid + '/sources' }, 'Подключить источник') : null));
      return;
    }
    list.appendChild(h('div', { class: 'cards' }, dashboards.map((d) => h('div', { class: 'card pad stack', style: { gap: '8px' } },
      h('a', { href: '#/d/' + d.id }, h('h3', { style: { margin: 0 } }, d.title)),
      d.description ? h('div', { class: 'muted small' }, d.description) : null,
      h('div', { class: 'row small muted' }, 'Период: ' + (G.RANGES.find((r) => r.value === d.default_range) || { label: d.default_range }).label, h('span', { class: 'spacer' }), 'изменён ' + G.fmtAgo(d.updated_at)),
      h('div', { class: 'row' },
        h('a', { class: 'btn sm primary', href: '#/d/' + d.id }, 'Открыть'),
        h('button', { class: 'btn sm', onclick: () => G.exportDashboard(d.id).catch((e) => G.toast(G.errMsg(e), 'error')) }, 'Экспорт'),
        canEdit ? h('button', {
          class: 'btn sm danger', onclick: async () => {
            if (!(await G.confirm('Удалить дашборд «' + d.title + '» со всеми панелями?', { danger: true, ok: 'Удалить' }))) return;
            await G.api.del('/dashboards/' + d.id);
            G.router.resolve();
          },
        }, 'Удалить') : null)))));
  };

  G.views.projectSettings = async function (el, params) {
    const pid = +params.pid;
    const { project, body } = await G.projectPage(el, pid, 'settings');
    const name = h('input', { value: project.name, required: true });
    const description = h('textarea', { rows: 4, value: project.description });
    const status = h('div', { class: 'notice error hidden' });
    body.appendChild(h('div', { class: 'card pad stack', style: { maxWidth: '640px' } },
      h('h2', null, 'Проект'),
      G.field('Название', name), G.field('Описание', description), status,
      h('div', { class: 'row' }, h('button', {
        class: 'btn primary', onclick: async () => {
          status.classList.add('hidden');
          try {
            await G.api.patch('/projects/' + pid, { name: name.value.trim(), description: description.value });
            await G.refreshMe();
            G.toast('Сохранено', 'ok');
            G.router.resolve();
          } catch (e) { status.textContent = G.errMsg(e); status.classList.remove('hidden'); }
        },
      }, 'Сохранить')),
      h('div', { class: 'muted small' }, 'Создан ' + G.fmtDate(project.created_at) + (project.created_by ? ' пользователем ' + (project.created_by.full_name || project.created_by.login) : ''))));

    const confirmInput = h('input', { placeholder: project.name });
    body.appendChild(h('div', { class: 'card pad stack', style: { maxWidth: '640px', marginTop: '16px', borderColor: 'var(--danger)' } },
      h('h2', { style: { color: 'var(--danger)' } }, 'Удаление проекта'),
      h('div', { class: 'muted' }, 'Будут удалены все дашборды, источники, сборщики с накопленными замерами и алерты проекта. Действие необратимо.'),
      G.field('Для подтверждения введите название проекта', confirmInput),
      h('div', null, h('button', {
        class: 'btn danger solid', onclick: async () => {
          if (confirmInput.value !== project.name) { G.toast('Название не совпадает', 'error'); return; }
          await G.api.del('/projects/' + pid);
          await G.refreshMe();
          G.toast('Проект удалён', 'ok');
          G.router.go('/projects');
        },
      }, 'Удалить проект'))));
  };
})(window.G);
