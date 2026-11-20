(function (G) {
  'use strict';
  const h = G.h;

  G.views = G.views || {};

  G.views.login = function (el) {
    if (G.api.token()) { G.router.go('/projects'); return; }
    const login = h('input', { autocomplete: 'username', required: true, value: G.storage.get('lastLogin', '') });
    const password = h('input', { type: 'password', autocomplete: 'current-password', required: true });
    const server = h('input', { value: G.settings.serverUrl(), placeholder: 'http://localhost:8000' });
    const error = h('div', { class: 'notice error hidden' });
    const submit = h('button', { class: 'btn primary', type: 'submit', style: { width: '100%' } }, 'Войти');
    const serverField = G.field('Сервер', server, 'Адрес сервера «Гриба» в сети компании');
    if (G.settings.sameOrigin) serverField.classList.add('hidden');

    const form = h('form', { class: 'card login stack' },
      h('div', { class: 'brand' }, h('img', { src: 'img/icon.svg', alt: '' }), 'Гриб'),
      G.field('Логин', login),
      G.field('Пароль', password),
      serverField,
      error,
      submit);

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      error.classList.add('hidden');
      submit.disabled = true;
      if (!G.settings.sameOrigin) G.settings.setServerUrl(server.value);
      try {
        await G.api.login(login.value.trim(), password.value);
        G.storage.set('lastLogin', login.value.trim());
        await G.app.afterLogin();
        G.router.go('/projects');
      } catch (err) {
        error.textContent = G.errMsg(err);
        error.classList.remove('hidden');
      } finally {
        submit.disabled = false;
      }
    });

    el.appendChild(h('div', { class: 'login-wrap' }, form));
    setTimeout(() => (login.value ? password : login).focus(), 30);
  };
})(window.G);
