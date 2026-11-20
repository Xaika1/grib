(function (G) {
  'use strict';
  const h = G.h;

  const TYPES = [
    { value: 'postgresql', label: 'PostgreSQL' },
    { value: 'mysql', label: 'MySQL / MariaDB' },
    { value: 'sqlite', label: 'SQLite (файл на сервере)' },
  ];
  const typeLabel = (t) => (TYPES.find((x) => x.value === t) || { label: t }).label;

  function sourceDialog(pid, src, onSaved) {
    const f = {
      name: h('input', { required: true, value: src ? src.name : '' }),
      type: G.select(TYPES, src ? src.type : 'postgresql'),
      host: h('input', { value: src ? src.host : '', placeholder: 'db.company.local' }),
      port: h('input', { type: 'number', min: 1, max: 65535, value: src && src.port ? src.port : '', placeholder: '5432' }),
      database: h('input', { value: src ? src.database : '' }),
      username: h('input', { value: src ? src.username : '', autocomplete: 'off' }),
      password: h('input', { type: 'password', autocomplete: 'new-password', placeholder: src && src.has_password ? 'не менять' : '' }),
    };
    const network = h('div', { class: 'stack' },
      h('div', { class: 'grid2' }, G.field('Сервер', f.host), G.field('Порт', f.port)),
      h('div', { class: 'grid2' }, G.field('Пользователь', f.username, 'Лучше завести пользователя только с правом чтения'), G.field('Пароль', f.password, 'Хранится на сервере в зашифрованном виде')));
    const dbField = G.field('База данных', f.database);
    const testResult = h('div', { class: 'notice hidden' });
    const sync = () => {
      const sqlite = f.type.value === 'sqlite';
      network.classList.toggle('hidden', sqlite);
      dbField.querySelector('span').textContent = sqlite ? 'Файл базы' : 'База данных';
      f.database.placeholder = sqlite ? 'shop.db — путь внутри каталога GRIB_SQLITE_DIR' : 'shop';
      f.port.placeholder = f.type.value === 'mysql' ? '3306' : '5432';
    };
    f.type.addEventListener('change', sync);
    sync();

    const payload = () => {
      const body = {
        name: f.name.value.trim(), type: f.type.value, host: f.host.value.trim(),
        port: f.port.value ? +f.port.value : null, database: f.database.value.trim(), username: f.username.value.trim(),
      };
      if (f.password.value || !src) body.password = f.password.value;
      return body;
    };

    G.modal({
      title: src ? 'Источник «' + src.name + '»' : 'Новый источник данных',
      body: h('div', { class: 'stack' }, h('div', { class: 'grid2' }, G.field('Название', f.name), G.field('Тип', f.type)), dbField, network,
        h('div', { class: 'muted small' }, '«Гриб» подключается к базе только для чтения и выполняет только запросы SELECT.'), testResult),
      actions: [
        {
          label: 'Проверить', keepOpen: true,
          onClick: async (ctx) => {
            testResult.className = 'notice';
            testResult.textContent = 'Подключаюсь…';
            try {
              const body = Object.assign(payload(), { name: 'test', source_id: src ? src.id : null });
              const res = await G.api.post('/projects/' + pid + '/sources/test', body);
              testResult.className = 'notice';
              testResult.style.color = 'var(--ok)';
              testResult.textContent = '✓ Подключение работает (' + res.elapsed_ms + ' мс)';
            } catch (e) {
              testResult.className = 'notice error';
              testResult.style.color = '';
              testResult.textContent = G.errMsg(e);
            }
            return false;
          },
        },
        { label: 'Отмена' },
        {
          label: 'Сохранить', kind: 'primary', submit: true,
          onClick: async () => {
            const res = src ? await G.api.patch('/sources/' + src.id, payload()) : await G.api.post('/projects/' + pid + '/sources', payload());
            G.toast('Источник сохранён', 'ok');
            onSaved(res);
          },
        },
      ],
    });
  }

  G.views.projectSources = async function (el, params) {
    const pid = +params.pid;
    const { project, body } = await G.projectPage(el, pid, 'sources');
    const canManage = project.can('source.manage');
    const reload = () => G.router.resolve();
    body.appendChild(h('div', { class: 'row', style: { marginBottom: '14px' } },
      canManage ? h('button', { class: 'btn primary', onclick: () => sourceDialog(pid, null, reload) }, '+ Источник') : null));
    const sources = await G.api.get('/projects/' + pid + '/sources');
    if (!sources.length) {
      body.appendChild(G.empty('Источников пока нет. Подключите базу данных компании, чтобы строить по ней графики.'));
      return;
    }
    body.appendChild(h('div', { class: 'card table-wrap' }, h('table', { class: 'list' },
      h('thead', null, h('tr', null, h('th', null, 'Название'), h('th', null, 'Тип'), h('th', null, 'Подключение'), h('th', null, ''))),
      h('tbody', null, sources.map((s) => h('tr', null,
        h('td', null, h('b', null, s.name)),
        h('td', null, typeLabel(s.type)),
        h('td', { class: 'mono muted' }, s.type === 'sqlite' ? s.database : (s.username ? s.username + '@' : '') + s.host + (s.port ? ':' + s.port : '') + '/' + s.database),
        h('td', { class: 'actions' }, canManage ? [
          h('button', { class: 'btn sm', onclick: () => sourceDialog(pid, s, reload) }, 'Изменить'), ' ',
          h('button', {
            class: 'btn sm danger', onclick: async () => {
              if (!(await G.confirm('Удалить источник «' + s.name + '»? Сборщики этого источника будут удалены вместе с замерами, а панели перестанут работать.', { danger: true, ok: 'Удалить' }))) return;
              await G.api.del('/sources/' + s.id);
              reload();
            },
          }, 'Удалить'),
        ] : null)))))));
  };
})(window.G);
