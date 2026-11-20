(function (G) {
  'use strict';
  const h = G.h;

  const PALETTE = ['#e8590c', '#1c7ed6', '#2f9e44', '#ae3ec9', '#f59f00', '#0ca678', '#e64980', '#4263eb', '#868e96', '#74b816'];
  G.PANEL_TYPES = [
    { value: 'line', label: 'Линия' },
    { value: 'bar', label: 'Столбцы' },
    { value: 'stat', label: 'Число' },
    { value: 'gauge', label: 'Шкала' },
    { value: 'table', label: 'Таблица' },
  ];

  function timeLabel(ms, spanMs) {
    const d = new Date(ms);
    if (spanMs > 2 * 86400e3) return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }) + ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: spanMs < 600e3 ? '2-digit' : undefined });
  }

  function lastValue(data) {
    const s = (data.series || [])[0];
    if (!s || !s.points.length) return null;
    for (let i = s.points.length - 1; i >= 0; i--) if (s.points[i][1] !== null) return { value: s.points[i][1], name: s.name, ts: s.points[i][0] };
    return null;
  }

  function msg(text, isError) { return h('div', { class: 'panel-msg' + (isError ? ' error' : '') }, text); }

  function lineView(body, panel, kind, period) {
    const canvas = h('canvas');
    body.appendChild(canvas);
    const st = panel.settings || {};
    const chart = new Chart(canvas, {
      type: kind,
      data: { datasets: [] },
      options: {
        animation: false,
        maintainAspectRatio: false,
        responsive: true,
        parsing: false,
        normalized: true,
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
        plugins: {
          legend: { display: true, position: 'bottom', labels: { boxWidth: 10, boxHeight: 10 } },
          tooltip: {
            callbacks: {
              title: (items) => items.length ? new Date(items[0].parsed.x).toLocaleString('ru-RU') : '',
              label: (item) => item.dataset.label + ': ' + G.fmtNum(item.parsed.y, st.decimals, st.unit),
            },
          },
        },
        scales: {
          x: { type: 'linear', ticks: { maxRotation: 0, autoSkipPadding: 16, callback(v) { return timeLabel(v, this.max - this.min); } }, grid: { display: false } },
          y: { beginAtZero: kind === 'bar', ticks: { callback: (v) => G.fmtNum(v, undefined, st.unit) } },
        },
        elements: { point: { radius: 0, hoverRadius: 3 }, line: { borderWidth: 2, tension: 0.25 } },
      },
    });
    return {
      update(data) {
        const series = data.series || [];
        chart.data.datasets = series.map((s, i) => ({
          label: s.name,
          data: s.points.map((p) => ({ x: p[0], y: p[1] })),
          borderColor: PALETTE[i % PALETTE.length],
          backgroundColor: kind === 'bar' ? PALETTE[i % PALETTE.length] + 'cc' : PALETTE[i % PALETTE.length] + '22',
          fill: kind === 'line' && series.length === 1,
          spanGaps: true,
          barPercentage: 0.9,
          categoryPercentage: 0.9,
        }));
        chart.options.plugins.legend.display = series.length > 1;
        const pr = period ? period() : null;
        chart.options.scales.x.min = pr ? pr.from : undefined;
        chart.options.scales.x.max = pr ? pr.to : undefined;
        chart.update('none');
      },
      destroy() { chart.destroy(); },
    };
  }

  function categoryBarView(body, panel) {
    const canvas = h('canvas');
    body.appendChild(canvas);
    const st = panel.settings || {};
    const chart = new Chart(canvas, {
      type: 'bar',
      data: { labels: [], datasets: [] },
      options: {
        animation: false,
        maintainAspectRatio: false,
        indexAxis: st.horizontal ? 'y' : 'x',
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (i) => G.fmtNum(i.raw, st.decimals, st.unit) } } },
        scales: {
          y: { beginAtZero: true, ticks: st.horizontal ? {} : { callback: (v) => G.fmtNum(v, undefined, st.unit) } },
          x: { beginAtZero: true, ticks: st.horizontal ? { callback: (v) => G.fmtNum(v, undefined, st.unit) } : {} },
        },
      },
    });
    return {
      update(data) {
        const items = (data.series || []).map((s) => {
          const v = lastValue({ series: [s] });
          return { name: s.name, value: v ? v.value : null };
        });
        chart.data.labels = items.map((x) => x.name);
        chart.data.datasets = [{ data: items.map((x) => x.value), backgroundColor: items.map((_, i) => PALETTE[i % PALETTE.length] + 'cc'), borderRadius: 4 }];
        chart.update('none');
      },
      destroy() { chart.destroy(); },
    };
  }

  function statView(body, panel) {
    const value = h('div', { class: 'value' });
    const label = h('div', { class: 'label' });
    body.appendChild(h('div', { class: 'stat' }, value, label));
    const st = panel.settings || {};
    return {
      update(data) {
        const v = lastValue(data);
        value.textContent = v ? G.fmtNum(v.value, st.decimals, st.unit) : '—';
        label.textContent = v ? v.name + ' · ' + new Date(v.ts).toLocaleTimeString('ru-RU') : 'нет данных';
        const thr = st.threshold !== undefined && st.threshold !== '' ? +st.threshold : null;
        value.style.color = v && thr !== null && v.value > thr ? 'var(--danger)' : '';
      },
      destroy() {},
    };
  }

  function gaugeView(body, panel) {
    const st = panel.settings || {};
    const min = st.min !== undefined && st.min !== '' ? +st.min : 0;
    const max = st.max !== undefined && st.max !== '' ? +st.max : 100;
    const canvas = h('canvas');
    const label = h('div', { class: 'gauge-value' });
    body.appendChild(canvas);
    body.appendChild(label);
    const chart = new Chart(canvas, {
      type: 'doughnut',
      data: { datasets: [{ data: [0, 1], backgroundColor: [PALETTE[0], 'rgba(127,127,127,.18)'], borderWidth: 0 }] },
      options: { animation: false, maintainAspectRatio: false, rotation: -90, circumference: 180, cutout: '72%', plugins: { legend: { display: false }, tooltip: { enabled: false } } },
    });
    return {
      update(data) {
        const v = lastValue(data);
        const val = v ? v.value : 0;
        const ratio = Math.max(0, Math.min(1, (val - min) / ((max - min) || 1)));
        const color = ratio > 0.85 ? '#e03131' : ratio > 0.65 ? '#f59f00' : '#2f9e44';
        chart.data.datasets[0].data = [ratio, 1 - ratio];
        chart.data.datasets[0].backgroundColor = [color, 'rgba(127,127,127,.18)'];
        chart.update('none');
        label.textContent = v ? G.fmtNum(val, st.decimals, st.unit) : '—';
      },
      destroy() { chart.destroy(); },
    };
  }

  function tableView(body) {
    const wrap = h('div', { class: 'panel-table' });
    body.appendChild(wrap);
    return {
      update(data) {
        const t = data.table || { columns: [], rows: [] };
        G.clear(wrap).appendChild(
          h('table', null,
            h('thead', null, h('tr', null, t.columns.map((c) => h('th', null, c)))),
            h('tbody', null, t.rows.slice(0, 1000).map((r) => h('tr', null, r.map((v) => h('td', null, v === null ? '∅' : typeof v === 'number' ? G.fmtNum(v) : String(v))))))));
      },
      destroy() {},
    };
  }

  G.panels = {
    PALETTE,

    create(body, panel, period) {
      let view = null;
      let viewKind = null;
      let data = null;
      let overlay = null;

      function ensure(kind) {
        if (viewKind === kind && view) return;
        if (view) view.destroy();
        G.clear(body);
        viewKind = kind;
        if (kind === 'line' || kind === 'bar-time') view = lineView(body, panel, kind === 'line' ? 'line' : 'bar', period);
        else if (kind === 'bar-cat') view = categoryBarView(body, panel);
        else if (kind === 'stat') view = statView(body, panel);
        else if (kind === 'gauge') view = gaugeView(body, panel);
        else view = tableView(body, panel);
      }

      function kindFor(d) {
        if (panel.type === 'bar') return d.time_column ? 'bar-time' : 'bar-cat';
        if (panel.type === 'line' && !d.time_column && panel.mode !== 'collector') return 'bar-cat';
        return panel.type;
      }

      function setOverlay(node) {
        if (overlay) overlay.remove();
        overlay = node;
        if (node) body.appendChild(node);
      }

      return {
        update(d) {
          data = d;
          ensure(kindFor(d));
          view.update(d);
          const empty = panel.type !== 'table' && !(d.series || []).some((s) => s.points.length);
          setOverlay(empty ? msg(d.table && d.table.rows.length ? 'В результате нет числовых столбцов' : 'Нет данных за выбранный период') : null);
        },

        append(ts, values, fromMs) {
          if (!data) data = { series: [], table: { columns: [], rows: [] }, time_column: 'time' };
          Object.keys(values).forEach((name) => {
            let s = data.series.find((x) => x.name === name);
            if (!s) { s = { name, points: [] }; data.series.push(s); }
            s.points.push([ts, values[name]]);
            if (fromMs) while (s.points.length && s.points[0][0] < fromMs) s.points.shift();
          });
          data.table = {
            columns: ['series', 'time', 'value'],
            rows: data.series.map((s) => { const p = s.points[s.points.length - 1]; return [s.name, new Date(p[0]).toLocaleString('ru-RU'), p[1]]; }),
          };
          this.update(data);
        },
        showError(e) {
          if (view) { view.destroy(); view = null; viewKind = null; }
          G.clear(body);
          overlay = null;
          body.appendChild(msg(G.errMsg(e), true));
        },
        loading() { if (!view) { G.clear(body); body.appendChild(msg('Загрузка…')); } },
        destroy() { if (view) view.destroy(); view = null; },
      };
    },
  };
})(window.G);
