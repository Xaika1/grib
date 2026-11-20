(function (G) {
  'use strict';
  const h = G.h;

  G.views.panelEditor = async function (el, params) {
    const did = +params.did;
    const isNew = params.panelId === 'new';
    const dash = await G.api.get('/dashboards/' + did);
    G.app.setProject(dash.project_id);
    const pid = dash.project_id;
    const panel = isNew
      ? { title: '', type: 'line', mode: 'live', source_id: null, collector_id: null, query: '', settings: {}, grid_w: 6, grid_h: 1 }
      : dash.panels.find((p) => p.id === +params.panelId);
    if (!panel) throw new Error('Панель не найдена');

    const [sources, collectors] = await Promise.all([
      G.can(pid, 'query.run') ? G.api.get('/projects/' + pid + '/source-names') : [],
      G.can(pid, 'collector.view') ? G.api.get('/projects/' + pid + '/collectors') : [],
    ]);
    const st = Object.assign({}, panel.settings || {});
    const initialModel = st.query_model || null;
    delete st.query_model;

    const title = h('input', { value: panel.title, placeholder: 'Например: Заказы по часам' });
    const type = G.select(G.PANEL_TYPES, panel.type);
    let mode = panel.mode;
    if (mode === 'live' && !sources.length && collectors.length) mode = 'collector';
    const modeSeg = G.seg([{ value: 'live', label: 'Прямой запрос' }, { value: 'collector', label: 'Сборщик' }], mode, (v) => { mode = v; syncMode(); refresh(); });
    const source = G.select(sources.map((s) => ({ value: s.id, label: s.name + ' · ' + s.type })), panel.source_id || (sources[0] && sources[0].id));
    const collector = G.select(collectors.map((c) => ({ value: c.id, label: c.name })), panel.collector_id || (collectors[0] && collectors[0].id));
    const unit = h('input', { value: st.unit || '', placeholder: '₽, шт, %' });
    const decimals = G.select([{ value: '', label: 'авто' }, 0, 1, 2, 3], st.decimals ?? '');
    const min = h('input', { type: 'number', step: 'any', value: st.min ?? '', placeholder: '0' });
    const max = h('input', { type: 'number', step: 'any', value: st.max ?? '', placeholder: '100' });
    const threshold = h('input', { type: 'number', step: 'any', value: st.threshold ?? '', placeholder: 'нет' });
    const width = G.select([{ value: 3, label: '¼' }, { value: 4, label: '⅓' }, { value: 6, label: '½' }, { value: 8, label: '⅔' }, { value: 12, label: 'вся ширина' }], panel.grid_w);
    const height = G.select([{ value: 1, label: 'обычная' }, { value: 2, label: 'двойная' }, { value: 3, label: 'тройная' }], panel.grid_h);
    const range = G.select(G.RANGES, dash.default_range);

    const liveBox = h('div', { class: 'stack' }, G.field('Источник данных', source));
    const editorBox = h('div');
    liveBox.appendChild(editorBox);
    const collectorBox = h('div', { class: 'stack' }, G.field('Сборщик', collector),
      h('div', { class: 'muted small' }, 'Панель покажет накопленные замеры сборщика, новые точки будут добавляться без перезагрузки.'));
    const gaugeBox = h('div', { class: 'grid2' }, G.field('Минимум шкалы', min), G.field('Максимум шкалы', max));
    const statBox = G.field('Подсветить, если больше', threshold);

    let query = { query: panel.query || '', model: initialModel, sql: panel.query || '' };
    let editor = null;
    if (sources.length) {
      editor = G.queryEditor(editorBox, {
        sourceId: +source.value,
        query: initialModel ? '' : panel.query,
        model: initialModel,
        sqlHint: 'SELECT created_at AS time, COUNT(*) AS orders\nFROM orders\nWHERE created_at >= $from AND created_at < $to\nGROUP BY 1',
        onChange(v) { query = v; refresh(); },
      });
      source.addEventListener('change', () => editor.setSource(+source.value));
    } else {
      editorBox.appendChild(h('div', { class: 'notice' }, G.can(pid, 'query.run') ? 'В проекте нет источников данных.' : 'У вас нет права выполнять запросы к источникам.'));
    }
    collector.addEventListener('change', () => refresh());

    function syncMode() {
      modeSeg.set(mode);
      liveBox.classList.toggle('hidden', mode !== 'live');
      collectorBox.classList.toggle('hidden', mode !== 'collector');
      gaugeBox.classList.toggle('hidden', type.value !== 'gauge');
      statBox.classList.toggle('hidden', type.value !== 'stat');
    }

    const status = h('div', { class: 'notice error hidden' });
    const saveBtn = h('button', { class: 'btn primary' }, isNew ? 'Добавить на дашборд' : 'Сохранить');

    const form = h('div', { class: 'card pad stack' },
      h('div', { class: 'grid2' }, G.field('Название', title), G.field('Тип', type)),
      h('div', { class: 'row' }, h('span', { class: 'muted small' }, 'Данные:'), modeSeg),
      liveBox, collectorBox,
      h('div', { class: 'grid2' }, G.field('Единица измерения', unit), G.field('Знаков после запятой', decimals)),
      gaugeBox, statBox,
      h('div', { class: 'grid2' }, G.field('Ширина', width), G.field('Высота', height)),
      status,
      h('div', { class: 'row' }, saveBtn, h('a', { class: 'btn', href: '#/d/' + did }, 'Отмена')));

    const previewBody = h('div', { class: 'panel-body' });
    const previewTitle = h('h3', null, panel.title || 'Предпросмотр');
    const sqlOut = h('pre', { class: 'sql-out mono hidden' });
    const meta = h('span', { class: 'muted small' });
    const preview = h('div', { class: 'preview stack' },
      h('div', { class: 'card panel' }, h('div', { class: 'panel-head' }, previewTitle, range), previewBody),
      h('div', { class: 'row' }, meta), sqlOut);
    let view = null;
    let seq = 0;

    function currentPanel() {
      const settings = {};
      if (unit.value.trim()) settings.unit = unit.value.trim();
      if (decimals.value !== '') settings.decimals = +decimals.value;
      if (type.value === 'gauge') { if (min.value !== '') settings.min = +min.value; if (max.value !== '') settings.max = +max.value; }
      if (type.value === 'stat' && threshold.value !== '') settings.threshold = +threshold.value;
      return {
        title: title.value.trim(), type: type.value, mode,
        source_id: mode === 'live' && source.value ? +source.value : null,
        collector_id: mode === 'collector' && collector.value ? +collector.value : null,
        settings, grid_w: +width.value, grid_h: +height.value,
      };
    }

    const refresh = G.debounce(async () => {
      const p = currentPanel();
      previewTitle.textContent = p.title || 'Предпросмотр';
      if (view) view.destroy();
      G.clear(previewBody);
      const to = Date.now();
      const from = to - G.rangeMs(range.value);
      view = G.panels.create(previewBody, p, () => ({ from, to }));
      const my = ++seq;
      const body = { project_id: pid, mode, from_ms: from, to_ms: to };
      if (mode === 'collector') {
        if (!p.collector_id) { view.showError('Выберите сборщик'); return; }
        body.collector_id = p.collector_id;
      } else {
        if (!p.source_id) { view.showError('Выберите источник данных'); return; }
        body.source_id = p.source_id;
        if (query.model) body.query_model = query.model; else body.query = query.query;
        if (!query.model && !query.query.trim()) { view.showError('Введите запрос'); return; }
      }
      view.loading();
      try {
        const data = await G.api.post('/query/preview', body);
        if (my !== seq) return;
        view.update(data);
        meta.textContent = mode === 'live'
          ? 'Строк: ' + data.table.rows.length + (data.truncated ? ' (обрезано)' : '') + ' · серий: ' + data.series.length + ' · ' + data.elapsed_ms + ' мс'
          : 'Серий: ' + data.series.length;
      } catch (e) {
        if (my !== seq) return;
        view.showError(e);
        meta.textContent = '';
      }
    }, 600);

    [title, unit, min, max, threshold].forEach((i) => i.addEventListener('input', refresh));
    [type, decimals, range].forEach((s) => s.addEventListener('change', () => { syncMode(); refresh(); }));

    saveBtn.addEventListener('click', async () => {
      status.classList.add('hidden');
      saveBtn.disabled = true;
      try {
        const body = currentPanel();
        if (mode === 'live') {
          const v = editor ? editor.value() : { query: '', model: null };
          if (v.model) body.query_model = v.model;
          else { body.query = v.query; if (!isNew) body.clear_query_model = true; }
        }
        if (isNew) await G.api.post('/dashboards/' + did + '/panels', body);
        else await G.api.patch('/panels/' + panel.id, body);
        G.toast('Панель сохранена', 'ok');
        G.router.go('/d/' + did);
      } catch (e) {
        status.textContent = G.errMsg(e);
        status.classList.remove('hidden');
      } finally {
        saveBtn.disabled = false;
      }
    });

    el.appendChild(h('div', { class: 'page-head' },
      h('div', null, h('div', { class: 'sub' }, h('a', { href: '#/d/' + did }, '← ' + dash.title)), h('h1', null, isNew ? 'Новая панель' : 'Редактирование панели'))));
    el.appendChild(h('div', { class: 'editor' }, form, preview));
    syncMode();
    refresh();

    return () => { refresh.cancel(); if (view) view.destroy(); };
  };
})(window.G);
