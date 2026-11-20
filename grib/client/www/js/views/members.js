(function (G) {
  'use strict';
  const h = G.h;

  G.views.projectMembers = async function (el, params) {
    const pid = +params.pid;
    const { project, body } = await G.projectPage(el, pid, 'members');
    const canManage = project.can('project.members');
    const reload = () => G.router.resolve();
    const [members, roles] = await Promise.all([G.api.get('/projects/' + pid + '/members'), G.api.get('/roles')]);
    const roleOptions = roles.map((r) => ({ value: r.id, label: r.name }));

    if (canManage) {
      const directory = await G.api.get('/users/directory');
      const available = directory.filter((u) => !members.some((m) => m.user.id === u.id));
      const userSel = G.select(available.map((u) => ({ value: u.id, label: (u.full_name ? u.full_name + ' — ' : '') + u.login })));
      const viewer = roles.find((r) => r.name === 'Наблюдатель');
      const roleSel = G.select(roleOptions, viewer ? viewer.id : roles[0].id);
      body.appendChild(h('div', { class: 'card pad', style: { marginBottom: '16px' } },
        h('h3', null, 'Добавить участника'),
        available.length ? h('div', { class: 'row' }, h('div', { class: 'grow', style: { minWidth: '200px' } }, userSel), roleSel,
          h('button', {
            class: 'btn primary', onclick: async () => {
              try {
                await G.api.post('/projects/' + pid + '/members', { user_id: +userSel.value, role_id: +roleSel.value });
                G.toast('Участник добавлен', 'ok');
                reload();
              } catch (e) { G.toast(G.errMsg(e), 'error'); }
            },
          }, 'Добавить'))
          : h('div', { class: 'muted' }, 'Все пользователи уже в проекте. Новых пользователей заводит администратор.')));
    }

    body.appendChild(h('div', { class: 'card table-wrap' }, h('table', { class: 'list' },
      h('thead', null, h('tr', null, h('th', null, 'Пользователь'), h('th', null, 'Роль'), h('th', null, ''))),
      h('tbody', null, members.map((m) => {
        let roleCell;
        if (canManage) {
          roleCell = G.select(roleOptions, m.role_id);
          roleCell.addEventListener('change', async () => {
            try {
              await G.api.patch('/projects/' + pid + '/members/' + m.id, { role_id: +roleCell.value });
              G.toast('Роль изменена', 'ok');
              await G.refreshMe();
            } catch (e) { G.toast(G.errMsg(e), 'error'); roleCell.value = m.role_id; }
          });
        } else roleCell = h('span', { class: 'badge accent' }, m.role);
        return h('tr', null,
          h('td', null, h('b', null, m.user.full_name || m.user.login), h('div', { class: 'muted small' }, m.user.login)),
          h('td', null, roleCell),
          h('td', { class: 'actions' }, canManage ? h('button', {
            class: 'btn sm danger', onclick: async () => {
              if (!(await G.confirm('Убрать «' + (m.user.full_name || m.user.login) + '» из проекта?', { danger: true, ok: 'Убрать' }))) return;
              try { await G.api.del('/projects/' + pid + '/members/' + m.id); reload(); } catch (e) { G.toast(G.errMsg(e), 'error'); }
            },
          }, 'Убрать') : null));
      })))));

    const roleHelp = h('details', { class: 'card pad', style: { marginTop: '16px' } }, h('summary', null, 'Что разрешает каждая роль'),
      h('div', { class: 'stack', style: { marginTop: '10px' } }, roles.map((r) => h('div', null, h('b', null, r.name), r.description ? ' — ' + r.description : '',
        h('div', { class: 'muted small mono' }, r.permissions.join(', ') || 'нет прав')))));
    body.appendChild(roleHelp);
  };
})(window.G);
