(function (G) {
  'use strict';

  const listeners = {};
  let socket = null;
  let retry = 0;
  let timer = null;
  let pingTimer = null;
  let wanted = false;
  let dashboardId = null;

  function emit(type, msg) {
    (listeners[type] || []).slice().forEach((fn) => { try { fn(msg); } catch (e) { console.error(e); } });
  }

  function send(obj) {
    if (socket && socket.readyState === 1) socket.send(JSON.stringify(obj));
  }

  function connect() {
    const token = G.api.token();
    if (!token) return;
    wanted = true;
    clearTimeout(timer);
    const url = G.settings.serverUrl().replace(/^http/, 'ws') + '/ws?token=' + encodeURIComponent(token);
    let ws;
    try { ws = new WebSocket(url); } catch (e) { schedule(); return; }
    socket = ws;
    ws.onopen = () => {
      retry = 0;
      emit('status', { online: true });
      if (dashboardId) send({ type: 'subscribe', dashboard_id: dashboardId });
      clearInterval(pingTimer);
      pingTimer = setInterval(() => send({ type: 'ping' }), 25000);
    };
    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      emit(msg.type, msg);
    };
    ws.onclose = (ev) => {
      clearInterval(pingTimer);
      if (socket === ws) socket = null;
      emit('status', { online: false });
      if (ev.code === 4401) { wanted = false; return; }
      if (wanted) schedule();
    };
    ws.onerror = () => { };
  }

  function schedule() {
    clearTimeout(timer);
    const delay = Math.min(30000, 1000 * Math.pow(2, retry++));
    timer = setTimeout(connect, delay);
  }

  G.ws = {
    connect,
    disconnect() {
      wanted = false;
      clearTimeout(timer);
      clearInterval(pingTimer);
      dashboardId = null;
      if (socket) { const s = socket; socket = null; s.close(); }
    },
    online() { return !!socket && socket.readyState === 1; },
    on(type, fn) {
      (listeners[type] = listeners[type] || []).push(fn);
      return () => { listeners[type] = (listeners[type] || []).filter((f) => f !== fn); };
    },
    subscribe(id) { dashboardId = id; send({ type: 'subscribe', dashboard_id: id }); },
    unsubscribe() { dashboardId = null; send({ type: 'unsubscribe' }); },
  };
})(window.G);
