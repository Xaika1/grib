window.G = window.G || {};

(function (G) {
  'use strict';

  G.h = function h(tag, props) {
    const el = document.createElement(tag);
    const p = props || {};
    for (const key of Object.keys(p)) {
      const v = p[key];
      if (v === undefined || v === null || v === false) continue;
      if (key === 'class') el.className = v;
      else if (key === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (key === 'dataset') Object.assign(el.dataset, v);
      else if (key.startsWith('on') && typeof v === 'function') el.addEventListener(key.slice(2), v);
      else if (key === 'value') el.value = v;
      else if (key === 'checked' || key === 'disabled' || key === 'selected' || key === 'multiple' || key === 'required') el[key] = !!v;
      else if (key === 'text') el.textContent = v;
      else el.setAttribute(key, v === true ? '' : v);
    }
    const add = (c) => {
      if (c === null || c === undefined || c === false) return;
      if (Array.isArray(c)) c.forEach(add);
      else el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
    };
    for (let i = 2; i < arguments.length; i++) add(arguments[i]);
    return el;
  };
  const h = G.h;

  G.clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

  G.storage = {
    get(key, def) {
      try { const v = localStorage.getItem('grib.' + key); return v === null ? def : JSON.parse(v); } catch (e) { return def; }
    },
    set(key, value) {
      try { localStorage.setItem('grib.' + key, JSON.stringify(value)); } catch (e) { }
    },
    remove(key) {
      try { localStorage.removeItem('grib.' + key); } catch (e) { }
    },
  };

  G.debounce = function (fn, ms) {
    let t = null;
    const d = function () { const args = arguments; clearTimeout(t); t = setTimeout(() => fn.apply(null, args), ms); };
    d.cancel = () => clearTimeout(t);
    return d;
  };

  G.parseDate = function (v) {
    if (v === null || v === undefined || v === '') return null;
    if (typeof v === 'number') return new Date(v);
    const s = String(v);
    return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : s + 'Z');
  };
  G.fmtDate = function (v, withSeconds) {
    const d = G.parseDate(v);
    if (!d || isNaN(d)) return '—';
    return d.toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: withSeconds ? '2-digit' : undefined,
    });
  };
  G.fmtAgo = function (v) {
    const d = G.parseDate(v);
    if (!d) return 'никогда';
    const s = Math.round((Date.now() - d.getTime()) / 1000);
    if (s < 5) return 'только что';
    if (s < 60) return s + ' с назад';
    if (s < 3600) return Math.round(s / 60) + ' мин назад';
    if (s < 86400) return Math.round(s / 3600) + ' ч назад';
    return G.fmtDate(v);
  };
  G.fmtNum = function (v, decimals, unit) {
    if (v === null || v === undefined || Number.isNaN(v)) return '—';
    let text;
    if (decimals !== undefined && decimals !== null && decimals !== '') {
      text = Number(v).toLocaleString('ru-RU', { minimumFractionDigits: +decimals, maximumFractionDigits: +decimals });
    } else {
      const abs = Math.abs(v);
      text = Number(v).toLocaleString('ru-RU', { maximumFractionDigits: abs >= 100 ? 0 : abs >= 1 ? 2 : 4 });
    }
    return unit ? text + ' ' + unit : text;
  };
  G.fmtDuration = function (sec) {
    sec = +sec || 0;
    if (sec === 0) return 'сразу';
    if (sec % 3600 === 0) return sec / 3600 + ' ч';
    if (sec % 60 === 0) return sec / 60 + ' мин';
    return sec + ' с';
  };

  G.errMsg = function (e) {
    if (!e) return 'Неизвестная ошибка';
    if (e.message) return e.message;
    return String(e);
  };

  G.toast = function (message, kind, timeout, title) {
    const box = document.getElementById('toasts');
    const el = h('div', { class: 'toast ' + (kind || ''), role: 'status' }, title ? h('b', null, title) : null, message);
    box.appendChild(el);
    const ms = timeout === undefined ? (kind === 'error' ? 6000 : 3500) : timeout;
    const close = () => el.remove();
    el.addEventListener('click', close);
    if (ms > 0) setTimeout(close, ms);
    return close;
  };

  G.modal = function (opts) {
    const back = h('div', { class: 'modal-back' });
    const errBox = h('div', { class: 'notice error hidden' });
    const close = () => { back.remove(); document.removeEventListener('keydown', onKey); if (opts.onClose) opts.onClose(); };
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    const footer = h('div', { class: 'modal-foot' });
    const ctx = {
      close,
      error(msg) { errBox.textContent = msg; errBox.classList.toggle('hidden', !msg); },
    };
    (opts.actions || [{ label: 'Закрыть' }]).forEach((a) => {
      const btn = h('button', { class: 'btn ' + (a.kind || ''), type: a.submit ? 'submit' : 'button' }, a.label);
      btn.addEventListener('click', async (ev) => {
        ev.preventDefault();
        if (!a.onClick) return close();
        ctx.error('');
        btn.disabled = true;
        try {
          const res = await a.onClick(ctx, btn);
          if (res !== false && a.keepOpen !== true) close();
        } catch (e) {
          ctx.error(G.errMsg(e));
        } finally {
          btn.disabled = false;
        }
      });
      footer.appendChild(btn);
    });
    const body = h('div', { class: 'modal-body' }, opts.body, errBox);
    const form = h('form', { class: 'modal' + (opts.wide ? ' wide' : ''), onsubmit: (e) => { e.preventDefault(); const s = footer.querySelector('button[type=submit]'); if (s) s.click(); } },
      h('div', { class: 'modal-head' }, h('h2', null, opts.title || ''), h('span', { class: 'spacer' }),
        h('button', { class: 'btn ghost icon', type: 'button', 'aria-label': 'Закрыть', onclick: close }, '✕')),
      body, footer);
    back.appendChild(form);
    back.addEventListener('mousedown', (e) => { if (e.target === back) close(); });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(back);
    const first = form.querySelector('.modal-body input, .modal-body select, .modal-body textarea');
    if (first) setTimeout(() => first.focus(), 30);
    return ctx;
  };

  G.confirm = function (text, opts) {
    const o = opts || {};
    return new Promise((resolve) => {
      let answered = false;
      G.modal({
        title: o.title || 'Подтверждение',
        body: h('p', { style: { margin: 0 } }, text),
        onClose: () => { if (!answered) resolve(false); },
        actions: [
          { label: 'Отмена' },
          { label: o.ok || 'Да', kind: o.danger ? 'danger solid' : 'primary', submit: true, onClick: () => { answered = true; resolve(true); } },
        ],
      });
    });
  };

  G.field = function (label, input, hint) {
    return h('label', { class: 'field' }, h('span', null, label), input, hint ? h('div', { class: 'hint' }, hint) : null);
  };
  G.select = function (options, value, props) {
    const sel = h('select', props || null);
    options.forEach((o) => {
      const opt = typeof o === 'object' ? o : { value: o, label: o };
      sel.appendChild(h('option', { value: String(opt.value), selected: String(opt.value) === String(value ?? '') }, opt.label));
    });
    return sel;
  };
  G.checkbox = function (label, checked, props) {
    const input = h('input', Object.assign({ type: 'checkbox', checked: !!checked }, props || {}));
    return { el: h('label', { class: 'check' }, input, label), input };
  };
  G.seg = function (options, value, onChange) {
    const wrap = h('div', { class: 'seg' });
    const buttons = options.map((o) => {
      const b = h('button', { type: 'button', class: o.value === value ? 'active' : '' }, o.label);
      b.addEventListener('click', () => {
        buttons.forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        onChange(o.value);
      });
      wrap.appendChild(b);
      return b;
    });
    wrap.set = (v) => buttons.forEach((b, i) => b.classList.toggle('active', options[i].value === v));
    return wrap;
  };

  G.download = function (filename, text) {
    const blob = new Blob([text], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = h('a', { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
  };

  G.pickFile = function (accept) {
    return new Promise((resolve) => {
      const input = h('input', { type: 'file', accept: accept || '' });
      input.addEventListener('change', () => {
        const file = input.files && input.files[0];
        if (!file) return resolve(null);
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.readAsText(file);
      });
      input.click();
    });
  };

  G.empty = (text, action) => h('div', { class: 'empty card' }, h('div', null, text), action ? h('div', { style: { marginTop: '12px' } }, action) : null);
  G.loading = () => h('div', { class: 'empty' }, 'Загрузка…');
  G.errorBox = (e) => h('div', { class: 'notice error' }, G.errMsg(e));

  G.RANGES = [
    { value: '15m', label: '15 минут' },
    { value: '1h', label: '1 час' },
    { value: '6h', label: '6 часов' },
    { value: '24h', label: '24 часа' },
    { value: '7d', label: '7 дней' },
    { value: '30d', label: '30 дней' },
  ];
  G.rangeMs = function (r) {
    const m = /^(\d+)([smhdw])$/.exec(r || '');
    if (!m) return 6 * 3600e3;
    return +m[1] * { s: 1e3, m: 60e3, h: 3600e3, d: 86400e3, w: 604800e3 }[m[2]];
  };
})(window.G);
