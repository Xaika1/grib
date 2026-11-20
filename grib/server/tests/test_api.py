from tests.conftest import auth


def login(client, login_, password):
    r = client.post("/api/auth/login", json={"login": login_, "password": password})
    assert r.status_code == 200, r.text
    return auth(r.json()["token"])


def test_login_rejects_bad_password(client):
    r = client.post("/api/auth/login", json={"login": "admin", "password": "nope"})
    assert r.status_code == 401


def test_requires_token(client):
    assert client.get("/api/projects").status_code == 401


def test_full_flow(client, admin):
    r = client.post("/api/projects", json={"name": "Магазин", "description": "демо"}, headers=admin)
    assert r.status_code == 201, r.text
    project = r.json()
    pid = project["id"]
    assert project["role"] == "Владелец проекта"
    assert "dashboard.edit" in project["permissions"]

    r = client.post(
        f"/api/projects/{pid}/sources/test", json={"type": "sqlite", "database": "shop.db"}, headers=admin
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/projects/{pid}/sources", json={"name": "shop", "type": "sqlite", "database": "../../etc/passwd"}, headers=admin
    )
    assert r.status_code == 400

    r = client.post(f"/api/projects/{pid}/sources", json={"name": "shop", "type": "sqlite", "database": "shop.db"}, headers=admin)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    r = client.get(f"/api/sources/{sid}/schema", headers=admin)
    assert r.status_code == 200
    tables = {t["name"]: t for t in r.json()["tables"]}
    assert {"orders", "queue_state"} <= set(tables)
    kinds = {c["name"]: c["kind"] for c in tables["orders"]["columns"]}
    assert kinds["created_at"] == "time" and kinds["amount"] == "number"

    model = {
        "table": "orders",
        "time": {"column": "created_at", "bucket": "hour"},
        "select": [{"column": "*", "agg": "count", "alias": "orders"}],
    }
    r = client.post("/api/query/build", json={"source_id": sid, "query_model": model}, headers=admin)
    assert r.status_code == 200, r.text
    assert "strftime" in r.json()["sql"]

    r = client.post("/api/query/preview", json={"project_id": pid, "source_id": sid, "query_model": model}, headers=admin)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["series"] and data["series"][0]["name"] == "orders"
    assert sum(p[1] for p in data["series"][0]["points"]) == 12

    r = client.post(
        "/api/query/preview", json={"project_id": pid, "source_id": sid, "query": "DELETE FROM orders"}, headers=admin
    )
    assert r.status_code == 400

    r = client.post(f"/api/projects/{pid}/dashboards", json={"title": "Продажи"}, headers=admin)
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    r = client.post(
        f"/api/dashboards/{did}/panels",
        json={"title": "Заказы", "type": "line", "source_id": sid, "query_model": model},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    panel = r.json()
    assert panel["settings"]["query_model"]["table"] == "orders"
    r = client.get(f"/api/panels/{panel['id']}/data", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["series"]

    r = client.patch(
        f"/api/panels/{panel['id']}",
        json={"query": "SELECT region, SUM(amount) AS revenue FROM orders GROUP BY region"},
        headers=admin,
    )
    assert r.status_code == 200 and "query_model" not in r.json()["settings"]

    r = client.post(
        f"/api/projects/{pid}/collectors",
        json={"name": "Очереди", "source_id": sid, "query": "SELECT name, size FROM queue_state", "interval_sec": 10},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = client.post(
        f"/api/projects/{pid}/alerts",
        json={"collector_id": cid, "name": "Очередь писем", "series": "emails", "operator": ">", "threshold": 10, "for_sec": 0},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    rule_id = r.json()["id"]

    r = client.post(f"/api/collectors/{cid}/run", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["values"] == {"orders": 5.0, "emails": 50.0}

    rules = client.get(f"/api/projects/{pid}/alerts", headers=admin).json()
    assert rules[0]["state"] == "firing"
    events = client.get(f"/api/projects/{pid}/alert-events", headers=admin).json()
    assert len(events) == 1 and events[0]["ended_at"] is None
    assert client.get("/api/alert-events/active", headers=admin).json()[0]["rule_id"] == rule_id

    r = client.post(
        f"/api/dashboards/{did}/panels",
        json={"title": "Очереди", "mode": "collector", "collector_id": cid},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    r = client.get(f"/api/panels/{r.json()['id']}/data", headers=admin)
    assert {s["name"] for s in r.json()["series"]} == {"orders", "emails"}

    exported = client.get(f"/api/dashboards/{did}/export", headers=admin).json()
    assert exported["panels"][0]["source"] == "shop"
    assert "password" not in str(exported)
    r = client.post(f"/api/projects", json={"name": "Копия"}, headers=admin)
    pid2 = r.json()["id"]
    r = client.post(f"/api/projects/{pid2}/dashboards/import", json={"data": exported}, headers=admin)
    assert r.status_code == 409
    assert r.json()["missing_sources"] == ["shop"] and r.json()["missing_collectors"] == ["Очереди"]
    r = client.post(
        f"/api/projects/{pid}/dashboards/import", json={"data": exported, "title": "Продажи (копия)"}, headers=admin
    )
    assert r.status_code == 201, r.text
    assert len(r.json()["panels"]) == 2

    r = client.post("/api/users", json={"login": "viewer", "password": "secret1", "full_name": "Наблюдатель"}, headers=admin)
    assert r.status_code == 201, r.text
    viewer_id = r.json()["id"]
    roles = {r_["name"]: r_ for r_ in client.get("/api/roles", headers=admin).json()}
    r = client.post(
        f"/api/projects/{pid}/members", json={"user_id": viewer_id, "role_id": roles["Наблюдатель"]["id"]}, headers=admin
    )
    assert r.status_code == 201, r.text
    member_id = r.json()["id"]

    viewer = login(client, "viewer", "secret1")
    assert [p["name"] for p in client.get("/api/projects", headers=viewer).json()] == ["Магазин"]
    assert client.get(f"/api/projects/{pid2}", headers=viewer).status_code == 403
    assert client.get(f"/api/panels/{panel['id']}/data", headers=viewer).status_code == 200
    assert client.get(f"/api/projects/{pid}/sources", headers=viewer).status_code == 403
    assert client.post(f"/api/projects/{pid}/dashboards", json={"title": "x"}, headers=viewer).status_code == 403
    r = client.post("/api/query/preview", json={"project_id": pid, "source_id": sid, "query": "SELECT 1"}, headers=viewer)
    assert r.status_code == 403
    assert client.get("/api/users", headers=viewer).status_code == 403
    assert client.post("/api/projects", json={"name": "Чужой"}, headers=viewer).status_code == 403

    r = client.post(
        "/api/roles",
        json={"name": "Аналитик", "permissions": ["dashboard.view", "dashboard.edit", "query.run"]},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    analyst_role = r.json()["id"]
    r = client.patch(f"/api/projects/{pid}/members/{member_id}", json={"role_id": analyst_role}, headers=admin)
    assert r.status_code == 200
    assert client.post(f"/api/projects/{pid}/dashboards", json={"title": "Мой"}, headers=viewer).status_code == 201
    assert client.delete(f"/api/roles/{analyst_role}", headers=admin).status_code == 400
    r = client.post("/api/roles", json={"name": "Плохая", "permissions": ["root"]}, headers=admin)
    assert r.status_code == 400

    members = client.get(f"/api/projects/{pid}/members", headers=admin).json()
    owner = next(m for m in members if m["role"] == "Владелец проекта")
    assert client.delete(f"/api/projects/{pid}/members/{owner['id']}", headers=admin).status_code == 400

    r = client.post("/api/auth/password", json={"old_password": "secret1", "new_password": "secret2"}, headers=viewer)
    assert r.status_code == 200
    assert client.get("/api/projects", headers=viewer).status_code == 401
    viewer = auth(r.json()["token"])
    assert client.get("/api/projects", headers=viewer).status_code == 200
    assert client.patch(f"/api/users/{viewer_id}", json={"password": "secret3"}, headers=admin).status_code == 200
    assert client.get("/api/projects", headers=viewer).status_code == 401
    viewer = login(client, "viewer", "secret3")

    r = client.post("/api/users", json={"login": "owner2", "password": "secret1"}, headers=admin)
    owner2 = login(client, "owner2", "secret1")
    client.patch(f"/api/users/{r.json()['id']}", json={"can_create_projects": True}, headers=admin)
    assert client.post("/api/projects", json={"name": "Свой"}, headers=owner2).status_code == 201
    r = client.delete(f"/api/users/{r.json()['id']}", headers=admin)
    assert r.status_code == 400 and "Свой" in r.json()["detail"]

    assert client.patch(f"/api/users/{viewer_id}", json={"is_blocked": True}, headers=admin).status_code == 200
    assert client.get("/api/projects", headers=viewer).status_code == 401


def test_websocket_receives_samples(client, admin):
    pid = client.post("/api/projects", json={"name": "WS"}, headers=admin).json()["id"]
    sid = client.post(
        f"/api/projects/{pid}/sources", json={"name": "shop", "type": "sqlite", "database": "shop.db"}, headers=admin
    ).json()["id"]
    cid = client.post(
        f"/api/projects/{pid}/collectors",
        json={"name": "q", "source_id": sid, "query": "SELECT name, size FROM queue_state", "interval_sec": 10},
        headers=admin,
    ).json()["id"]
    did = client.post(f"/api/projects/{pid}/dashboards", json={"title": "d"}, headers=admin).json()["id"]
    client.post(f"/api/dashboards/{did}/panels", json={"mode": "collector", "collector_id": cid}, headers=admin)

    token = admin["Authorization"].split()[1]
    with client.websocket_connect(f"/ws?token={token}") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "subscribe", "dashboard_id": did})
        assert ws.receive_json()["collectors"] == [cid]
        client.post(f"/api/collectors/{cid}/run", headers=admin)
        msg = ws.receive_json()
        assert msg["type"] == "sample" and msg["collector_id"] == cid
        assert msg["values"]["emails"] == 50.0


def test_websocket_rejects_bad_token(client):
    with client.websocket_connect("/ws?token=bad") as ws:
        assert ws.receive_json()["type"] == "error"
