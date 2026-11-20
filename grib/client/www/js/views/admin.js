(function (G) {
  'use strict';
  const h = G.h;

  function userDialog(user, onSaved) {
    const login = h('input', { required: true, value: user ? user.login : '', disabled: !!user, autocomplete: 'off' });
    const fullName = h('input', { value: user ? user.full_name : '' });
    const password = h('input', { type: 'password', autocomplete: 'new-password', placeholder: user ? 'оставьте пустым, чтобы не менять' : 'не короче 4 символов' });
    const isAdmin = G.checkbox('Администратор системы — видит все проекты, управляет пользователями и ролями', user ? user.is_admin : false);
    const canCreate = G.checkbox('Может создавать проекты', user ? user.can_create_projects : false);
    const blocked = G.checkbox('Заблокирован — не может войти', user ? user.is_blocked : false);
    G.modal({
      title: user ? 'Пользователь ' + user.login : 'Новый пользователь',
      body: h('div', { class: 'stack' },
        h('div', { class: 'grid2' }, G.field('Логин', login), G.field('ФИО', fullName)),
        G.field(user ? 'Новый пароль (сброс)' : 'Пароль', password),
        isAdmin.el, canCreate.el, user ? blocked.el : null),
      actions: [
        { label: 'Отмена' },
        {
          label: 'Сохранить', kind: 'primary', submit: true,
          onClick: async () => {
            if (user) {
              const body = { full_name: fullName.value.trim(), is_admin: isAdmin.input.checked, can_create_projects: canCreate.input.checked, is_blocked: blocked.input.checked };
              if (password.value) body.password = password.value;
              await G.api.patch('/users/' + user.id, body);
            } else {
              await G.api.post('/users', { login: login.value.trim(), full_name: fullName.value.trim(), password: password.value, is_admin: isAdmin.input.checked, can_create_projects: canCreate.input.checked });
            }
            G.toast('Пользователь сохранён', 'ok');
            onSaved();
          },
        },
      ],
    });
  }

  G.views.adminUsers = async function (el) {
    const reload = () => G.router.resolve();
    const search = h('input', { type: 'search', placeholder: 'Поиск по логину или ФИО', value: G.storage.get('userSearch', '') });
    el.appendChild(h('div', { class: 'page-head' },
      h('div', null, h('h1', null, 'Пользователи'), h('div', { class: 'sub' }, 'Учётные записи «Гриба». Доступ к проектам выдаётся на вкладке «Участники» проекта.')),
      h('span', { class: 'spacer' }),
      h('button', { class: 'btn primary', onclick: () => userDialog(null, reload) }, '+ Пользователь')));
    el.appendChild(h('div', { class: 'row', style: { marginBottom: '14px' } }, h('div', { class: 'grow', style: { maxWidth: '360px' } }, search)));
    const list = h('div');
    el.appendChild(list);

    async function load() {
      G.storage.set('userSearch', search.value);
      const users = await G.api.get('/users?q=' + encodeURIComponent(search.value.trim()));
      G.clear(list);
      if (!users.length) { list.appendChild(G.empty('Никого не нашлось.')); return; }
      list.appendChild(h('div', { class: 'card table-wrap' }, h('table', { class: 'list' },
        h('thead', null, h('tr', null, ['Пользователь', 'Права', 'Создан', ''].map((t) => h('th', null, t)))),
        h('tbody', null, users.map((u) => h('tr', { style: u.is_blocked ? { opacity: '.6' } : null },
          h('td', null, h('b', null, u.full_name || u.login), h('div', { class: 'muted small' }, u.login)),
          h('td', null, h('div', { class: 'row' },
            u.is_admin ? h('span', { class: 'badge accent' }, 'администратор') : null,
            u.can_create_projects && !u.is_admin ? h('span', { class: 'badge' }, 'создаёт проекты') : null,
            u.is_blocked ? h('span', { class: 'badge danger' }, 'заблокирован') : null)),
          h('td', { class: 'muted' }, G.fmtDate(u.created_at)),
          h('td', { class: 'actions' },
            h('button', { class: 'btn sm', onclick: () => userDialog(u, load) }, 'Изменить'), ' ',
            u.id !== G.state.me.user.id ? h('button', {
              class: 'btn sm danger', onclick: async () => {
                if (!(await G.confirm('Удалить пользователя «' + u.login + '»? Он будет убран из всех проектов. Вместо удаления можно заблокировать.', { danger: true, ok: 'Удалить' }))) return;
                try { await G.api.del('/users/' + u.id); load(); } catch (e) { G.toast(G.errMsg(e), 'error'); }
              },
            }, 'Удалить') : null)))))));
    }
    search.addEventListener('input', G.debounce(load, 300));
    await load();
  };

  function roleDialog(role, onSaved) {
    const name = h('input', { required: true, value: role ? role.name : '', disabled: role && role.is_builtin });
    const description = h('input', { value: role ? role.description : '' });
    G.modal({
      title: role ? 'Роль «' + role.name + '»' : 'Новая роль',
      body: h('div', { class: 'stack' }, G.field('Название', name), G.field('Описание', description),
        role ? null : h('div', { class: 'muted small' }, 'Права роли отмечаются галочками в таблице после создания.')),
      actions: [
        { label: 'Отмена' },
        {
          label: 'Сохранить', kind: 'primary', submit: true,
          onClick: async () => {
            const body = { description: description.value.trim() };
            if (!role || !role.is_builtin) body.name = name.value.trim();
            if (role) await G.api.patch('/roles/' + role.id, body);
            else await G.api.post('/roles', Object.assign({ permissions: ['dashboard.view'] }, body));
            onSaved();
          },
        },
      ],
    });
  }

  G.views.adminRoles = async function (el) {
    const reload = () => G.router.resolve();
    el.appendChild(h('div', { class: 'page-head' },
      h('div', null, h('h1', null, 'Ролевая модель'), h('div', { class: 'sub' }, 'Роль — набор прав внутри проекта. Изменения применяются сразу ко всем участникам с этой ролью.')),
      h('span', { class: 'spacer' }),
      h('button', { class: 'btn primary', onclick: () => roleDialog(null, reload) }, '+ Роль')));
    const [roles, perms] = await Promise.all([G.api.get('/roles'), G.api.get('/permissions')]);

    const toggle = async (role, code, input) => {
      const set = new Set(role.permissions);
      if (input.checked) set.add(code); else set.delete(code);
      input.disabled = true;
      try {
        const res = await G.api.patch('/roles/' + role.id, { permissions: Array.from(set) });
        role.permissions = res.permissions;
        G.toast('Права роли «' + role.name + '» обновлены', 'ok', 1800);
      } catch (e) {
        input.checked = !input.checked;
        G.toast(G.errMsg(e), 'error');
      } finally {
        input.disabled = false;
      }
    };

    const head = h('tr', null, h('th', null, 'Право'), roles.map((r) => h('th', null,
      h('div', null, h('b', null, r.name)),
      h('div', { class: 'muted small' }, r.is_builtin ? 'встроенная' : 'своя', ' · ', G.plural(r.members, 'участник', 'участника', 'участников')),
      h('div', { class: 'row', style: { justifyContent: 'center', marginTop: '4px' } },
        h('button', { class: 'btn ghost sm', onclick: () => roleDialog(r, reload) }, '✎'),
        r.is_builtin ? null : h('button', {
          class: 'btn ghost sm danger', title: 'Удалить роль', onclick: async () => {
            if (!(await G.confirm('Удалить роль «' + r.name + '»?', { danger: true, ok: 'Удалить' }))) return;
            try { await G.api.del('/roles/' + r.id); reload(); } catch (e) { G.toast(G.errMsg(e), 'error'); }
          },
        }, '✕')))));
    const rows = perms.map((p) => h('tr', null,
      h('td', null, h('div', null, p.description), h('div', { class: 'muted small mono' }, p.code)),
      roles.map((r) => {
        const input = h('input', { type: 'checkbox', checked: r.permissions.indexOf(p.code) !== -1, 'aria-label': r.name + ': ' + p.code });
        input.addEventListener('change', () => toggle(r, p.code, input));
        return h('td', null, input);
      })));
    el.appendChild(h('div', { class: 'card table-wrap' }, h('table', { class: 'matrix' }, h('thead', null, head), h('tbody', null, rows))));
    el.appendChild(h('p', { class: 'muted small' }, 'Администратор системы имеет все права во всех проектах независимо от роли. Создавать проекты могут администраторы и пользователи с отметкой «Может создавать проекты».'));
  };
})(window.G);
