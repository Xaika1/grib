(function (G) {
  'use strict';
  const h = G.h;

  const AGGS = [
    { value: 'none', label: 'значение' },
    { value: 'count', label: 'COUNT' },
    { value: 'sum', label: 'SUM' },
    { value: 'avg', label: 'AVG' },
    { value: 'min', label: 'MIN' },
    { value: 'max', label: 'MAX' },
  ];
  const BUCKETS = [
    { value: 'minute', label: 'по минутам' },
    { value: 'hour', label: 'по часам' },
    { value: 'day', label: 'по дням' },
    { value: 'none', label: 'без группировки' },
  ];
  const OPS = ['=', '!=', '>', '>=', '<', '<=', 'like', 'not like', 'in', 'is null', 'is not null'];

  function emptyModel(table) {
    return { table: table || '', time: null, select: [], where: [], where_mode: 'and', group_by: [], order_by: [], limit: null };
  }

  function suggest(table) {
    const m = emptyModel(table.name);
    const timeCol = table.columns.find((c) => c.kind === 'time');
    if (timeCol) m.time = { column: timeCol.name, bucket: 'hour', filter: true };
    m.select = [{ column: '*', agg: 'count', alias: 'count' }];
    return m;
  }

  G.builder = {
    emptyModel,
    create(container, opts) {
      const schema = opts.schema || { tables: [] };
      let model = opts.model ? JSON.parse(JSON.stringify(opts.model)) : null;
      if (!model && schema.tables.length) model = suggest(schema.tables[0]);
      if (!model) model = emptyModel('');
      model.select = model.select || [];
      model.where = model.where || [];
      model.group_by = model.group_by || [];
      model.order_by = model.order_by || [];

      const changed = () => opts.onChange && opts.onChange(JSON.parse(JSON.stringify(model)));
      const table = () => schema.tables.find((t) => t.name === model.table) || { name: model.table, columns: [] };
      const colOptions = (extra) => (extra || []).concat(table().columns.map((c) => ({ value: c.name, label: c.name + '  · ' + c.type.toLowerCase() })));

      function onSel(sel, fn, rerender) {
        sel.addEventListener('change', () => { fn(sel.value); if (rerender) render(); changed(); });
        return sel;
      }
      function onInput(input, fn) {
        input.addEventListener('input', () => { fn(input.value); changed(); });
        return input;
      }
      const removeBtn = (fn) => h('button', { type: 'button', class: 'btn ghost sm icon', title: 'Удалить', onclick: () => { fn(); render(); changed(); } }, '✕');
      const addBtn = (label, fn) => h('button', { type: 'button', class: 'btn ghost sm', onclick: () => { fn(); render(); changed(); } }, '+ ' + label);

      function render() {
        G.clear(container);
        const root = h('div', { class: 'builder' });
        if (!schema.tables.length) {
          root.appendChild(h('div', { class: 'notice' }, 'В источнике нет таблиц, доступных для чтения.'));
          container.appendChild(root);
          return;
        }

        root.appendChild(h('div', { class: 'group' }, h('div', { class: 'title' }, 'Таблица'),
          onSel(G.select(schema.tables.map((t) => t.name), model.table), (v) => {
            const t = schema.tables.find((x) => x.name === v);
            model = t ? suggest(t) : emptyModel(v);
          }, true)));

        const timeCols = table().columns.filter((c) => c.kind === 'time' || /date|time|_at$/i.test(c.name));
        const timeGroup = h('div', { class: 'group' }, h('div', { class: 'title' }, 'Время'));
        if (model.time) {
          timeGroup.appendChild(h('div', { class: 'item' },
            onSel(G.select(colOptions(), model.time.column), (v) => { model.time.column = v; }),
            onSel(G.select(BUCKETS, model.time.bucket), (v) => { model.time.bucket = v; }),
            (() => { const c = G.checkbox('только выбранный период', model.time.filter !== false); c.input.addEventListener('change', () => { model.time.filter = c.input.checked; changed(); }); return c.el; })(),
            removeBtn(() => { model.time = null; })));
        } else {
          timeGroup.appendChild(h('div', { class: 'item' },
            h('span', { class: 'muted small' }, 'Без столбца времени запрос вернёт «снимок» — подходит для столбцов, числа и шкалы.'),
            addBtn('столбец времени', () => { model.time = { column: (timeCols[0] || table().columns[0] || {}).name, bucket: 'hour', filter: true }; })));
        }
        root.appendChild(timeGroup);

        const sel = h('div', { class: 'group' }, h('div', { class: 'title' }, 'Значения'));
        model.select.forEach((item, i) => {
          sel.appendChild(h('div', { class: 'item' },
            onSel(G.select(AGGS, item.agg), (v) => { item.agg = v; if (v !== 'count' && item.column === '*') item.column = (table().columns[0] || {}).name; }, true),
            onSel(G.select(colOptions(item.agg === 'count' ? [{ value: '*', label: '* (все строки)' }] : []), item.column), (v) => { item.column = v; }),
            onInput(h('input', { placeholder: 'название', value: item.alias || '', style: { width: '130px' } }), (v) => { item.alias = v.trim() || null; }),
            removeBtn(() => { model.select.splice(i, 1); })));
        });
        sel.appendChild(h('div', null, addBtn('значение', () => {
          const num = table().columns.find((c) => c.kind === 'number');
          model.select.push(num ? { column: num.name, agg: 'sum', alias: null } : { column: '*', agg: 'count', alias: null });
        })));
        root.appendChild(sel);

        const where = h('div', { class: 'group' }, h('div', { class: 'title' }, 'Фильтры',
          model.where.length > 1 ? onSel(G.select([{ value: 'and', label: 'все условия (И)' }, { value: 'or', label: 'любое условие (ИЛИ)' }], model.where_mode), (v) => { model.where_mode = v; }) : null));
        model.where.forEach((c, i) => {
          const needsValue = c.op !== 'is null' && c.op !== 'is not null';
          where.appendChild(h('div', { class: 'item' },
            onSel(G.select(colOptions(), c.column), (v) => { c.column = v; }),
            onSel(G.select(OPS, c.op), (v) => { c.op = v; }, true),
            needsValue ? onInput(h('input', { placeholder: c.op === 'in' ? 'a, b, c' : 'значение', value: c.value === null || c.value === undefined ? '' : String(c.value) }), (v) => {
              const col = table().columns.find((x) => x.name === c.column);
              c.value = col && col.kind === 'number' && c.op !== 'in' && v.trim() !== '' && !isNaN(+v) ? +v : v;
            }) : null,
            removeBtn(() => { model.where.splice(i, 1); })));
        });
        where.appendChild(h('div', null, addBtn('условие', () => { model.where.push({ column: (table().columns[0] || {}).name, op: '=', value: '' }); })));
        root.appendChild(where);

        const group = h('div', { class: 'group' }, h('div', { class: 'title' }, 'Разбить на серии по'));
        const chips = h('div', { class: 'chips' });
        table().columns.filter((c) => c.kind === 'text').forEach((c) => {
          const on = model.group_by.indexOf(c.name) !== -1;
          chips.appendChild(h('span', {
            class: 'chip' + (on ? ' on' : ''),
            onclick: () => {
              if (on) model.group_by = model.group_by.filter((x) => x !== c.name); else model.group_by.push(c.name);
              render(); changed();
            },
          }, c.name));
        });
        if (!chips.childNodes.length) chips.appendChild(h('span', { class: 'muted small' }, 'Нет текстовых столбцов'));
        group.appendChild(chips);
        root.appendChild(group);

        const order = h('div', { class: 'group' }, h('div', { class: 'title' }, 'Сортировка и лимит'));
        const sortable = [];
        if (model.time) sortable.push({ value: 'time', label: 'time (время)' });
        model.select.forEach((s) => {
          const name = s.alias || (s.agg === 'none' ? s.column : s.column === '*' ? 'count' : s.agg + '_' + s.column);
          if (name && !sortable.some((x) => x.value === name)) sortable.push({ value: name, label: name });
        });
        table().columns.forEach((c) => { if (!sortable.some((x) => x.value === c.name)) sortable.push({ value: c.name, label: c.name }); });
        model.order_by.forEach((o, i) => {
          order.appendChild(h('div', { class: 'item' },
            onSel(G.select(sortable, o.column), (v) => { o.column = v; }),
            onSel(G.select([{ value: 'asc', label: 'по возрастанию' }, { value: 'desc', label: 'по убыванию' }], o.dir), (v) => { o.dir = v; }),
            removeBtn(() => { model.order_by.splice(i, 1); })));
        });
        order.appendChild(h('div', { class: 'item' },
          addBtn('сортировка', () => { model.order_by.push({ column: (sortable[0] || {}).value, dir: 'desc' }); }),
          h('span', { class: 'spacer' }),
          h('span', { class: 'muted small' }, 'не больше'),
          onInput(h('input', { type: 'number', min: 1, max: 100000, placeholder: '∞', value: model.limit || '', style: { width: '90px' } }), (v) => { model.limit = v ? Math.max(1, Math.min(100000, parseInt(v, 10) || 1)) : null; }),
          h('span', { class: 'muted small' }, 'строк')));
        root.appendChild(order);

        container.appendChild(root);
      }

      render();
      changed();
      return {
        model: () => JSON.parse(JSON.stringify(model)),
      };
    },
  };
})(window.G);
