(function (G) {
  'use strict';
  const h = G.h;

  const STATE = { ok: 'норма', pending: 'ожидание', firing: 'сработал' };
  const OPS = ['>', '>=', '<', '<=', '==', '!='];

  async function ruleDialog(pid, rule, collectors, onSaved) {
    if (!collectors.length) { G.toast('Алерты строятся по сборщикам. Сначала создайте сборщик.', 'error'); return; }
    const name = h('input', { required: true, value: rule ? rule.name : '' });
    const collector = G.select(collectors.map((c) => ({ value: c.id, label: c.name })), rule ? rule.collector_id : collectors[0].id);
    const series = G.select([{ value: '', label: 'первая серия' }], '');
    const op = G.select(OPS, rule ? rule.operator : '>');
    const threshold = h('input', { type: 'number', step: 'any', required: true, value: rule ? rule.threshold : '' });
    const forMin = h('input', { type: 'number', min: 0, step: 'any', value: rule ? rule.for_sec / 60 : 5 });
    const enabled = G.checkbox('Включено', rule ? rule.enabled : true);

    async function loadSeries() {
      const names = await G.api.get('/collectors/' + collector.value + '/series').catch(() => []);
      const current = rule && String(rule.collector_id) === collector.value ? rule.series : series.value;
      G.clear(series);
      series.appendChild(h('option', { value: '' }, 'первая серия'));
      const all = names.slice();
      if (current && all.indexOf(current) === -1) all.push(current);
      all.forEach((n) => series.appendChild(h('option', { value: n, selected: n === current }, n)));
    }
    collector.addEventListener('change', loadSeries);
    loadSeries();

    G.modal({
      title: rule ? 'Правило «' + rule.name + '»' : 'Новое правило алерта',
      body: h('div', { class: 'stack' },
        G.field('Название', name),
        h('div', { class: 'grid2' }, G.field('Сборщик', collector), G.field('Серия', series, 'Серии появляются после первого замера')),
        h('div', { class: 'grid3' }, G.field('Условие', op), G.field('Порог', threshold), G.field('Дольше, мин', forMin, '0 — сработать сразу')),
        h('div', { class: 'muted small' }, 'Пока порог превышен меньше заданного времени, правило в состоянии «ожидание» — так кратковременные выбросы не вызывают тревогу.'),
        enabled.el),
      actions: [
        { label: 'Отмена' },
        {
          label: 'Сохранить', kind: 'primary', submit: true,
          onClick: async () => {
            const body = {
              name: name.value.trim(), series: series.value || null, operator: op.value,
              threshold: parseFloat(threshold.value), for_sec: Math.round((parseFloat(forMin.value) || 0) * 60), enabled: enabled.input.checked,
            };
            if (Number.isNaN(body.threshold)) throw new Error('Укажите порог числом');
            if (rule) await G.api.patch('/alerts/' + rule.id, body);
            else await G.api.post('/projects/' + pid + '/alerts', Object.assign({ collector_id: +collector.value }, body));
            onSaved();
          },
        },
      ],
    });
  }

  G.views.projectAlerts = async function (el, params) {
    const pid = +params.pid;
    const { project, body } = await G.projectPage(el, pid, 'alerts');
    const canManage = project.can('alert.manage');
    const reload = () => G.router.resolve();
    const [rules, events, collectors] = await Promise.all([
      G.api.get('/projects/' + pid + '/alerts'),
      G.api.get('/projects/' + pid + '/alert-events?limit=100'),
      G.api.get('/projects/' + pid + '/collectors').catch(() => []),
    ]);
    const collectorName = (id) => (collectors.find((c) => c.id === id) || { name: '#' + id }).name;

    body.appendChild(h('div', { class: 'row', style: { marginBottom: '14px' } },
      canManage ? h('button', { class: 'btn primary', onclick: () => ruleDialog(pid, null, collectors, reload) }, '+ Правило') : null));

    if (!rules.length) body.appendChild(G.empty('Правил пока нет. Алерт проверяется после каждого замера сборщика.'));
    else {
      body.appendChild(h('div', { class: 'card table-wrap' }, h('table', { class: 'list' },
        h('thead', null, h('tr', null, ['Правило', 'Сборщик', 'Условие', 'Последнее значение', 'Состояние', ''].map((t) => h('th', null, t)))),
        h('tbody', null, rules.map((r) => h('tr', null,
          h('td', null, h('b', null, r.name), r.enabled ? null : h('span', { class: 'badge', style: { marginLeft: '6px' } }, 'выключено')),
          h('td', null, collectorName(r.collector_id), r.series ? h('div', { class: 'muted small' }, 'серия: ' + r.series) : null),
          h('td', { class: 'mono' }, r.operator + ' ' + G.fmtNum(r.threshold) + (r.for_sec ? ' дольше ' + G.fmtDuration(r.for_sec) : '')),
          h('td', null, G.fmtNum(r.last_value), r.last_eval_at ? h('div', { class: 'muted small' }, G.fmtAgo(r.last_eval_at)) : null),
          h('td', null, h('span', { class: 'badge ' + r.state }, STATE[r.state] || r.state)),
          h('td', { class: 'actions' }, canManage ? [
            h('button', { class: 'btn sm', onclick: () => ruleDialog(pid, r, collectors, reload) }, 'Изменить'), ' ',
            h('button', {
              class: 'btn sm danger', onclick: async () => {
                if (!(await G.confirm('Удалить правило «' + r.name + '» вместе с историей срабатываний?', { danger: true, ok: 'Удалить' }))) return;
                await G.api.del('/alerts/' + r.id);
                reload();
              },
            }, 'Удалить'),
          ] : null)))))));
    }

    body.appendChild(h('h2', { style: { marginTop: '24px' } }, 'Лента срабатываний'));
    if (!events.length) body.appendChild(G.empty('Алерты ещё не срабатывали.'));
    else {
      body.appendChild(h('div', { class: 'card table-wrap' }, h('table', { class: 'list' },
        h('thead', null, h('tr', null, ['Начало', 'Окончание', 'Правило', 'Значение', ''].map((t) => h('th', null, t)))),
        h('tbody', null, events.map((e) => h('tr', null,
          h('td', null, G.fmtDate(e.started_at, true)),
          h('td', null, e.ended_at ? G.fmtDate(e.ended_at, true) : h('span', { class: 'badge firing' }, 'активен')),
          h('td', null, h('b', null, e.rule_name), h('div', { class: 'muted small' }, e.message)),
          h('td', null, G.fmtNum(e.value)),
          h('td', { class: 'muted small' }, e.ended_at ? 'длился ' + G.fmtDuration(Math.round((G.parseDate(e.ended_at) - G.parseDate(e.started_at)) / 1000)) : '')))))));
    }

    const off = G.ws.on('alert', (msg) => { if (msg.project_id === pid) reload(); });
    return off;
  };
})(window.G);
