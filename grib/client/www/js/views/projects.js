(function (G) {
  'use strict';
  const h = G.h;

  function plural(n, one, few, many) {
    const m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return n + ' ' + one;
    if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return n + ' ' + few;
    return n + ' ' + many;
  }
  G.plural = plural;

  G.createProjectDialog = function () {
    const name = h('input', { required: true, maxlength: 200 });
    const description = h('textarea', { rows: 3, maxlength: 5000 });
    G.modal({
      title: 'Новый проект',
      body: h('div', { class: 'stack' },
        G.field('Название', name),
        G.field('Описание', description, 'Чем занимается команда, какие системы мониторит'),
        h('div', { class: 'muted small' }, 'Вы станете владельцем проекта и сможете добавить участников.')),
      actions: [
        { label: 'Отмена' },
        {
          label: 'Создать', kind: 'primary', submit: true,
          onClick: async () => {
            const p = await G.api.post('/projects', { name: name.value.trim(), description: description.value });
            await G.refreshMe();
            G.toast('Проект «' + p.name + '» создан', 'ok');
            G.router.go('/p/' + p.id + '/dashboards');
          },
        },
      ],
    });
  };

  G.views.projects = async function (el) {
    const me = G.state.me;
    const canCreate = me.user.is_admin || me.user.can_create_projects;
    el.appendChild(h('div', { class: 'page-head' },
      h('div', null, h('h1', null, 'Проекты'), h('div', { class: 'sub' }, 'Рабочие пространства команд: источники, дашборды, сборщики и алерты')),
      h('span', { class: 'spacer' }),
      canCreate ? h('button', { class: 'btn primary', onclick: G.createProjectDialog }, '+ Новый проект') : null));
    const list = h('div', null, G.loading());
    el.appendChild(list);

    const projects = await G.api.get('/projects');
    G.clear(list);
    if (!projects.length) {
      list.appendChild(G.empty(
        canCreate ? 'Пока нет ни одного проекта.' : 'Вас ещё не добавили ни в один проект. Обратитесь к администратору или владельцу проекта.',
        canCreate ? h('button', { class: 'btn primary', onclick: G.createProjectDialog }, 'Создать первый проект') : null));
      return;
    }
    list.appendChild(h('div', { class: 'cards' }, projects.map((p) => h('a', { class: 'card link', href: '#/p/' + p.id + '/dashboards' },
      h('h3', null, p.name),
      p.description ? h('div', { class: 'muted small', style: { marginBottom: '10px' } }, p.description.length > 140 ? p.description.slice(0, 140) + '…' : p.description) : null,
      h('div', { class: 'row small muted' },
        h('span', null, plural(p.counts.dashboards || 0, 'дашборд', 'дашборда', 'дашбордов')),
        h('span', null, '·'),
        h('span', null, plural(p.counts.members || 0, 'участник', 'участника', 'участников'))),
      h('div', { style: { marginTop: '10px' } }, h('span', { class: 'badge accent' }, p.role || '—'))))));
  };
})(window.G);
