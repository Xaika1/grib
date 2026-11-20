(function (G) {
  'use strict';
  const h = G.h;

  const schemaCache = new Map();

  G.loadSchema = async function (sourceId, refresh) {
    if (!refresh && schemaCache.has(sourceId)) return schemaCache.get(sourceId);
    const data = await G.api.get('/sources/' + sourceId + '/schema' + (refresh ? '?refresh=true' : ''));
    schemaCache.set(sourceId, data);
    return data;
  };

  G.queryEditor = function (container, opts) {
    let sourceId = opts.sourceId || null;
    let mode = opts.model ? 'builder' : (opts.query ? 'sql' : 'builder');
    let model = opts.model || null;
    let query = opts.query || '';
    let builtSql = '';
    let seq = 0;

    const area = h('div', { class: 'stack' });
    const segCtl = G.seg([{ value: 'builder', label: 'Билдер' }, { value: 'sql', label: 'SQL' }], mode, (v) => {
      if (v === 'sql' && mode === 'builder' && builtSql) query = builtSql;
      mode = v;
      render();
      emit();
    });
    container.appendChild(h('div', { class: 'stack' }, h('div', { class: 'row' }, segCtl, h('span', { class: 'spacer' }),
      h('span', { class: 'muted small' }, 'Макросы: $from, $to — границы периода, $interval — шаг в секундах')), area));

    function emit() {
      if (opts.onChange) opts.onChange({ query: mode === 'sql' ? query : '', model: mode === 'builder' ? model : null, sql: mode === 'builder' ? builtSql : query });
    }

    const buildSql = G.debounce(async (m, out) => {
      const my = ++seq;
      try {
        const res = await G.api.post('/query/build', { source_id: sourceId, query_model: m });
        if (my !== seq) return;
        builtSql = res.sql;
        out.textContent = res.sql;
        out.classList.remove('error-text');
        emit();
      } catch (e) {
        if (my !== seq) return;
        builtSql = '';
        out.textContent = G.errMsg(e);
        out.classList.add('error-text');
      }
    }, 300);

    async function render() {
      G.clear(area);
      segCtl.set(mode);
      if (mode === 'sql') {
        const ta = h('textarea', { class: 'sql', spellcheck: 'false', placeholder: opts.sqlHint || 'SELECT …', value: query });
        ta.addEventListener('input', () => { query = ta.value; emit(); });
        ta.addEventListener('keydown', (e) => {
          if (e.key === 'Tab') { e.preventDefault(); const s = ta.selectionStart; ta.setRangeText('  ', s, ta.selectionEnd, 'end'); query = ta.value; emit(); }
        });
        area.appendChild(ta);
        if (model) area.appendChild(h('div', { class: 'muted small' }, 'После ручной правки запрос нельзя вернуть в билдер — модель билдера будет удалена при сохранении.'));
        return;
      }
      if (!sourceId) { area.appendChild(h('div', { class: 'notice' }, 'Сначала выберите источник данных.')); return; }
      const holder = h('div');
      const out = h('pre', { class: 'sql-out mono' }, '…');
      area.appendChild(holder);
      area.appendChild(h('div', { class: 'row' }, h('span', { class: 'muted small' }, 'Собранный SQL'), h('span', { class: 'spacer' }),
        h('button', { type: 'button', class: 'btn ghost sm', onclick: () => { if (builtSql) { query = builtSql; mode = 'sql'; render(); emit(); } } }, 'Редактировать как SQL'),
        h('button', { type: 'button', class: 'btn ghost sm', onclick: async () => { await G.loadSchema(sourceId, true); render(); } }, '↻ Обновить схему')));
      area.appendChild(out);
      holder.appendChild(G.loading());
      let schema;
      try {
        schema = await G.loadSchema(sourceId);
      } catch (e) {
        G.clear(holder).appendChild(G.errorBox(e));
        out.remove();
        return;
      }
      G.clear(holder);
      const knownTable = model && schema.tables.some((t) => t.name === model.table);
      G.builder.create(holder, {
        schema,
        model: knownTable ? model : null,
        onChange(m) { model = m; buildSql(m, out); },
      });
    }

    render();
    return {
      value: () => ({ query: mode === 'sql' ? query : '', model: mode === 'builder' ? model : null, mode }),
      setSource(id) {
        if (String(id || '') === String(sourceId || '')) return;
        sourceId = id ? +id : null;
        if (mode === 'builder') { model = null; builtSql = ''; }
        render();
        emit();
      },
    };
  };
})(window.G);
