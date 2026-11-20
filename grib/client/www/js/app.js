(function (G) {
  'use strict';
  const h = G.h;

  const root = document.getElementById('app');
  let nav = null;
  let content = null;
  let currentRoute = null;

  function link(href, label, active, extra) {
    return h('a', { href, class: active ? 'active' : '' }, label, extra || null);
  }

  function renderNav() {
    if (!nav) return;
    const me = G.state.me;
    const path = G.router.current();
    const pid = G.state.projectId;
    G.clear(nav);
    nav.appendChild(h('a', { class: 'brand', href: '#/projects' }, h('img', { src: 'img/icon.svg', alt: '' }), 'Гриб'));
    const alerts = G.notify.count();
    nav.appendChild(link('#/projects', 'Проекты', path === '/projects', alerts ? h('span', { class: 'badge firing', title: 'Активные алерты' }, alerts) : null));

    if (pid && me) {
      const project = me.projects.find((p) => p.id === pid);
      if (project || me.user.is_admin) {
        nav.appendChild(h('div', { class: 'nav-title' }, project ? project.name : 'Проект #' + pid));
        G.PROJECT_TABS.forEach((t) => {
          if (t.perm && !G.can(pid, t.perm)) return;
          const href = '/p/' + pid + '/' + t.key;
          const active = path === href || (t.key === 'dashboards' && /^\/d\//.test(path));
          nav.appendChild(link('#' + href, t.label, active));
        });
      }
    }
    if (me && me.user.is_admin) {
      nav.appendChild(h('div', { class: 'nav-title' }, 'Администрирование'));
      nav.appendChild(link('#/admin/users', 'Пользователи', path === '/admin/users'));
      nav.appendChild(link('#/admin/roles', 'Ролевая модель', path === '/admin/roles'));
    }
    nav.appendChild(h('div', { class: 'nav-foot' },
      link('#/settings', 'Настройки', path === '/settings'),
      h('a', { href: '#/login', onclick: (e) => { e.preventDefault(); G.api.logout(); } }, 'Выйти'),
      me ? h('div', { class: 'nav-user', title: me.user.login }, me.user.full_name || me.user.login) : null));
  }

  function closeNav() {
    if (nav) nav.classList.remove('open');
    const b = document.querySelector('.nav-backdrop');
    if (b) b.remove();
  }

  G.app = {
    mount(route, params) {
      currentRoute = route;
      closeNav();
      if (route.public) {
        nav = null;
        content = null;
        G.clear(root);
        const el = h('div');
        root.appendChild(el);
        return el;
      }
      if (!params.pid && !route.keepProject) G.state.projectId = null;
      if (params.pid) G.state.projectId = +params.pid;
      if (!nav || !document.body.contains(nav)) {
        G.clear(root);
        nav = h('nav', { class: 'nav' });
        content = h('main', { class: 'content' });
        const topbar = h('header', { class: 'topbar' },
          h('button', {
            class: 'btn ghost icon', 'aria-label': 'Меню', onclick: () => {
              nav.classList.add('open');
              document.body.appendChild(h('div', { class: 'nav-backdrop', onclick: closeNav }));
            },
          }, '☰'),
          h('a', { class: 'brand', href: '#/projects' }, h('img', { src: 'img/icon.svg', alt: '' }), 'Гриб'));
        root.appendChild(h('div', { class: 'shell' }, nav, h('div', { class: 'grow', style: { minWidth: 0 } }, topbar, content)));
      }
      renderNav();
      G.clear(content);
      window.scrollTo(0, 0);
      return content;
    },
    setProject(pid) {
      G.state.projectId = +pid;
      renderNav();
    },
    async afterLogin() {
      await G.refreshMe();
      G.ws.connect();
      G.notify.load();
      G.notify.requestPermission();
    },
  };

  G.notify.onChange(renderNav);

  const r = G.router;
  r.add('/login', G.views.login, { public: true });
  r.add('/projects', G.views.projects);
  r.add('/p/:pid', (el, p) => G.router.go('/p/' + p.pid + '/dashboards'));
  r.add('/p/:pid/dashboards', G.views.projectDashboards);
  r.add('/p/:pid/sources', G.views.projectSources);
  r.add('/p/:pid/collectors', G.views.projectCollectors);
  r.add('/p/:pid/alerts', G.views.projectAlerts);
  r.add('/p/:pid/members', G.views.projectMembers);
  r.add('/p/:pid/settings', G.views.projectSettings);
  r.add('/d/:did', G.views.dashboard, { keepProject: true });
  r.add('/d/:did/panel/:panelId', G.views.panelEditor, { keepProject: true });
  r.add('/admin/users', G.views.adminUsers);
  r.add('/admin/roles', G.views.adminRoles);
  r.add('/settings', G.views.settings);

  (async function start() {
    G.themes.apply();
    if (G.api.token()) {
      try {
        await G.app.afterLogin();
      } catch (e) {
        if (e.status !== 401) {
          G.clear(root).appendChild(h('div', { class: 'login-wrap' }, h('div', { class: 'card pad stack', style: { maxWidth: '420px' } },
            h('h2', null, 'Не удалось подключиться к серверу'), h('div', { class: 'muted' }, G.errMsg(e)),
            h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: () => location.reload() }, 'Повторить'),
              h('button', { class: 'btn', onclick: () => G.api.logout() }, 'Сменить сервер')))));
          window.addEventListener('hashchange', () => location.reload(), { once: true });
          return;
        }
      }
    }
    if (!G.api.token() && location.hash !== '#/login') location.hash = '#/login';
    r.start();
  })();
})(window.G);
