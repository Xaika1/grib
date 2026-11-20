(function (G) {
  'use strict';
  const h = G.h;

  G.views.settings = async function (el) {
    el.appendChild(h('div', { class: 'page-head' }, h('h1', null, 'Настройки')));
    const wrap = h('div', { class: 'stack', style: { maxWidth: '640px' } });
    el.appendChild(wrap);

    wrap.appendChild(h('div', { class: 'card pad stack' }, h('h2', null, 'Оформление'),
      G.seg([{ value: 'system', label: 'Как в системе' }, { value: 'light', label: 'Светлая' }, { value: 'dark', label: 'Тёмная' }], G.settings.theme(), (v) => G.themes.set(v)),
      h('div', { class: 'muted small' }, 'Выбор сохраняется на этом устройстве.')));

    const server = h('input', { value: G.settings.serverUrl(), placeholder: 'http://grib.company.local:8000' });
    const serverStatus = h('div', { class: 'small muted' });
    wrap.appendChild(h('div', { class: 'card pad stack' }, h('h2', null, 'Сервер'),
      G.field('Адрес сервера', server, G.settings.sameOrigin ? 'Веб-версия открыта с сервера «Гриба», адрес можно не менять.' : 'Все данные приложение берёт с этого сервера.'),
      h('div', { class: 'row' },
        h('button', {
          class: 'btn', onclick: async () => {
            serverStatus.textContent = 'Проверяю…';
            try {
              const r = await fetch(server.value.replace(/\/+$/, '') + '/api/health');
              const d = await r.json();
              serverStatus.textContent = d.status === 'ok' ? '✓ Сервер отвечает' : 'Неожиданный ответ сервера';
            } catch (e) { serverStatus.textContent = '✕ Сервер недоступен'; }
          },
        }, 'Проверить'),
        h('button', {
          class: 'btn primary', onclick: () => {
            const changed = server.value.replace(/\/+$/, '') !== G.settings.serverUrl();
            G.settings.setServerUrl(server.value);
            if (changed) { G.toast('Адрес сервера изменён — войдите заново', 'ok'); G.api.logout(); }
          },
        }, 'Сохранить'),
        serverStatus)));

    const oldPw = h('input', { type: 'password', autocomplete: 'current-password' });
    const newPw = h('input', { type: 'password', autocomplete: 'new-password' });
    const newPw2 = h('input', { type: 'password', autocomplete: 'new-password' });
    const pwStatus = h('div', { class: 'notice hidden' });
    wrap.appendChild(h('div', { class: 'card pad stack' }, h('h2', null, 'Смена пароля'),
      G.field('Текущий пароль', oldPw), h('div', { class: 'grid2' }, G.field('Новый пароль', newPw), G.field('Ещё раз', newPw2)), pwStatus,
      h('div', null, h('button', {
        class: 'btn primary', onclick: async () => {
          pwStatus.className = 'notice error';
          if (newPw.value !== newPw2.value) { pwStatus.textContent = 'Пароли не совпадают'; return; }
          try {
            const res = await G.api.post('/auth/password', { old_password: oldPw.value, new_password: newPw.value });
            G.api.setToken(res.token);
            G.ws.disconnect();
            G.ws.connect();
            pwStatus.className = 'notice';
            pwStatus.textContent = '✓ Пароль изменён';
            oldPw.value = newPw.value = newPw2.value = '';
          } catch (e) { pwStatus.textContent = G.errMsg(e); }
        },
      }, 'Сменить пароль'))));

    const me = G.state.me.user;
    wrap.appendChild(h('div', { class: 'muted small' }, 'Вы вошли как ' + (me.full_name || me.login) + ' (' + me.login + '). «Гриб» 0.1.0'));
  };
})(window.G);
