(function (G) {
  'use strict';

  const active = new Map();
  const listeners = [];

  function changed() { listeners.forEach((fn) => fn(active.size)); }

  function systemNotify(title, body) {
    try {
      if (!('Notification' in window)) return;
      if (Notification.permission === 'granted' && document.hidden) new Notification(title, { body, icon: 'img/icon.svg' });
    } catch (e) { }
  }

  G.ws.on('alert', (msg) => {
    if (msg.state === 'firing') {
      active.set(msg.rule_id, msg);
      G.toast(msg.message || msg.name, 'firing', 10000, '🔥 Алерт: ' + msg.name);
      systemNotify('Алерт: ' + msg.name, msg.message || '');
    } else if (msg.state === 'ok' && msg.previous === 'firing') {
      active.delete(msg.rule_id);
      G.toast('Значение вернулось в норму: ' + G.fmtNum(msg.value), 'ok', 5000, '✓ ' + msg.name);
    } else if (msg.state === 'pending') {
      G.toast('Порог превышен, ждём подтверждения', 'warn', 4000, '⏳ ' + msg.name);
    }
    changed();
  });

  G.notify = {
    async load() {
      try {
        const events = await G.api.get('/alert-events/active');
        active.clear();
        events.forEach((e) => active.set(e.rule_id, e));
        changed();
      } catch (e) { }
    },
    count() { return active.size; },
    onChange(fn) { listeners.push(fn); return () => listeners.splice(listeners.indexOf(fn), 1); },
    requestPermission() {
      try { if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission(); } catch (e) { }
    },
  };
})(window.G);
