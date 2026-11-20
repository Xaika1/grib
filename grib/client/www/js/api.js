(function (G) {
  'use strict';

  class ApiError extends Error {
    constructor(message, status, data) {
      super(message);
      this.status = status;
      this.data = data || {};
    }
  }

  G.ApiError = ApiError;

  G.api = {
    token() { return G.storage.get('token', null); },
    setToken(t) { if (t) G.storage.set('token', t); else G.storage.remove('token'); },

    async request(method, path, body, opts) {
      const headers = { Accept: 'application/json' };
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      const token = this.token();
      if (token) headers.Authorization = 'Bearer ' + token;
      let res;
      try {
        res = await fetch(G.settings.serverUrl() + '/api' + path, {
          method,
          headers,
          body: body === undefined ? undefined : JSON.stringify(body),
        });
      } catch (e) {
        throw new ApiError('Сервер недоступен: ' + G.settings.serverUrl(), 0);
      }
      if (res.status === 204) return null;
      let data = null;
      try { data = await res.json(); } catch (e) { data = null; }
      if (!res.ok) {
        const detail = data && typeof data.detail === 'string' ? data.detail : 'Ошибка ' + res.status;
        if (res.status === 401 && !(opts && opts.noAuthRedirect)) {
          this.setToken(null);
          G.state.me = null;
          if (G.ws) G.ws.disconnect();
          if (location.hash !== '#/login') location.hash = '#/login';
        }
        throw new ApiError(detail, res.status, data);
      }
      return data;
    },
    get(path) { return this.request('GET', path); },
    post(path, body) { return this.request('POST', path, body === undefined ? {} : body); },
    patch(path, body) { return this.request('PATCH', path, body); },
    put(path, body) { return this.request('PUT', path, body); },
    del(path) { return this.request('DELETE', path); },

    async login(login, password) {
      const data = await this.request('POST', '/auth/login', { login, password }, { noAuthRedirect: true });
      this.setToken(data.token);
      return data;
    },
    logout() {
      this.setToken(null);
      G.state.me = null;
      if (G.ws) G.ws.disconnect();
      location.hash = '#/login';
    },
  };

  G.state = { me: null, projectId: null };

  G.can = function (projectId, permission) {
    const me = G.state.me;
    if (!me) return false;
    if (me.user.is_admin) return true;
    const p = me.projects.find((x) => x.id === +projectId);
    return !!p && p.permissions.indexOf(permission) !== -1;
  };

  G.refreshMe = async function () {
    G.state.me = await G.api.get('/auth/me');
    return G.state.me;
  };
})(window.G);
