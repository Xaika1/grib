(function (G) {
  'use strict';
  const h = G.h;

  const INTERVALS = [
    { value: 5, label: '5 с' }, { value: 10, label: '10 с' }, { value: 30, label: '30 с' }, { value: 60, label: '1 мин' },
    { value: 300, label: '5 мин' }, { value: 900, label: '15 мин' }, { value: 3600, label: '1 ч' },
  ];

  async function collectorDialog(pid, col, onSaved) {
    const sources = await G.api.get('/projects/' + pid + '/source-names').catch(() => []);
    if (!sources.length) { G.toast('Сначала подключите источник данных', 'error'); return; }
    const name = h('input', { required: true, value: col ? col.name : '' });
    const source = G.select(sources.map((s) => ({ value: s.id, label: s.name })), col ? col.source_id : sources[0].id);
    const interval = G.select(INTERVALS.some((i) => col && i.value === col.interval_sec) || !col ? INTERVALS : INTERVALS.concat([{ value: col.interval_sec, label: col.interval_sec + ' с' }]), col ? col.interval_sec : 60);
    const enabled = G.checkbox('Включён', col ? col.enabled : true);
    const editorBox = h('div');
    const result = h('div', { class: 'notice hidden' });
    const editor = G.queryEditor(editorBox, {
      sourceId: +source.value,
      query: col ? col.query : '',
      model: col ? col.query_model : null,
      sqlHint: 'SELECT name, size FROM queue_state  -- без столбца времени: одно значение на серию',
    });
    source.addEventListener('change', () => editor.setSource(+source.value));

    const payload = () => {
      const v = editor.value();
      const body = { name: name.value.trim(), source_id: +source.value, interval_sec: +interval.value, enabled: enabled.input.checked };
      if (v.model) body.query_model = v.model; else { body.query = v.query; if (col) body.clear_query_model = true; }
      return body;
    };

    G.modal({
      title: col ? 'Сборщик «' + col.name + '»' : 'Новый сборщик',
      wide: true,
      body: h('div', { class: 'stack' },
        h('div', { class: 'muted small' }, 'Каждое выполнение сохраняется с меткой времени. Каждый числовой столбец (или пара «метка — число») становится серией.'),
        h('div', { class: 'grid3' }, G.field('Название', name), G.field('Источник', source), G.field('Интервал', interval)),
        enabled.el, editorBox, result),
      actions: [
        {
          label: 'Проверить запрос', keepOpen: true,
          onClick: async () => {
            const v = editor.value();
            result.className = 'notice';
            result.textContent = 'Выполняю…';
            try {
              const now = Date.now();
              const res = await G.api.post('/query/preview', {
                project_id: pid, source_id: +source.value, query: v.query, query_model: v.model,
                from_ms: now - (+interval.value) * 1000, to_ms: now,
              });
              const values = res.series.map((s) => { const p = s.points[s.points.length - 1]; return s.name + ' = ' + G.fmtNum(p ? p[1] : null); });
              result.className = values.length ? 'notice' : 'notice error';
              result.textContent = values.length ? 'Будут сохраняться серии: ' + values.join(', ') : 'Запрос не вернул числовых значений — сборщику нечего сохранять.';
            } catch (e) {
              result.className = 'notice error';
              result.textContent = G.errMsg(e);
            }
            return false;
          },
        },
        { label: 'Отмена' },
        {
          label: 'Сохранить', kind: 'primary', submit: true,
          onClick: async () => {
            const res = col ? await G.api.patch('/collectors/' + col.id, payload()) : await G.api.post('/projects/' + pid + '/collectors', payload());
            G.toast('Сборщик сохранён', 'ok');
            onSaved(res);
          },
        },
      ],
    });
  }

  G.views.projectCollectors = async function (el, params) {
    const pid = +params.pid;
    const { project, body } = await G.projectPage(el, pid, 'collectors');
    const canManage = project.can('collector.manage');
    const reload = () => G.router.resolve();
    body.appendChild(h('div', { class: 'row', style: { marginBottom: '14px' } },
      canManage ? h('button', { class: 'btn primary', onclick: () => collectorDialog(pid, null, reload) }, '+ Сборщик') : null,
      h('span', { class: 'muted small' }, 'Нужны, когда база хранит только текущее значение (размер очереди, число пользователей онлайн).')));
    const [collectors, sources] = await Promise.all([
      G.api.get('/projects/' + pid + '/collectors'),
      project.can('query.run') ? G.api.get('/projects/' + pid + '/source-names').catch(() => []) : [],
    ]);
    if (!collectors.length) { body.appendChild(G.empty('Сборщиков пока нет.')); return; }
    const sourceName = (id) => (sources.find((s) => s.id === id) || { name: '#' + id }).name;
    body.appendChild(h('div', { class: 'card table-wrap' }, h('table', { class: 'list' },
      h('thead', null, h('tr', null, ['Название', 'Источник', 'Интервал', 'Последний запуск', 'Состояние', ''].map((t) => h('th', null, t)))),
      h('tbody', null, collectors.map((c) => h('tr', null,
        h('td', null, h('b', null, c.name), c.query_model ? h('span', { class: 'badge', style: { marginLeft: '6px' } }, 'билдер') : null),
        h('td', null, sourceName(c.source_id)),
        h('td', null, G.fmtDuration(c.interval_sec)),
        h('td', { title: c.last_run_at ? G.fmtDate(c.last_run_at, true) : '' }, G.fmtAgo(c.last_run_at)),
        h('td', null, !c.enabled ? h('span', { class: 'badge' }, 'выключен')
          : c.last_error ? h('span', { class: 'badge danger', title: c.last_error }, 'ошибка')
            : h('span', { class: 'badge ok' }, 'работает'),
        c.last_error ? h('div', { class: 'error-text small', style: { maxWidth: '360px' } }, c.last_error) : null),
        h('td', { class: 'actions' }, canManage ? [
          h('button', {
            class: 'btn sm', onclick: async (e) => {
              e.target.disabled = true;
              try {
                const r = await G.api.post('/collectors/' + c.id + '/run');
                if (r.error) G.toast(r.error, 'error');
                else G.toast(Object.keys(r.values).map((k) => k + ' = ' + G.fmtNum(r.values[k])).join(', '), 'ok', 5000, 'Замер сохранён');
                reload();
              } finally { e.target.disabled = false; }
            },
          }, '▶ Запустить'), ' ',
          h('button', { class: 'btn sm', onclick: () => collectorDialog(pid, c, reload) }, 'Изменить'), ' ',
          h('button', {
            class: 'btn sm danger', onclick: async () => {
              if (!(await G.confirm('Удалить сборщик «' + c.name + '» вместе с накопленными замерами и правилами алертов?', { danger: true, ok: 'Удалить' }))) return;
              await G.api.del('/collectors/' + c.id);
              reload();
            },
          }, 'Удалить'),
        ] : null)))))));
  };
})(window.G);
