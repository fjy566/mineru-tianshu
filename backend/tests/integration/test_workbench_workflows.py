"""工作台主要按钮对应的 API 流程；全部使用临时目录和临时数据库。"""

import pytest
from fastapi.testclient import TestClient
from auth.models import UserRole
from tests.integration.test_task_config_api import load_api_module, make_token


@pytest.fixture
def workbench(runtime_paths):
    headers = make_token(runtime_paths, UserRole.ADMIN)
    api = load_api_module()
    with TestClient(api.app) as client:
        yield api, client, headers


def test_profile_user_and_token_lifecycle(workbench):
    api, client, headers = workbench
    me = client.get("/api/v1/auth/me", headers=headers).json()
    updated = client.patch("/api/v1/auth/me", json={"full_name": "QA profile"}, headers=headers)
    assert updated.status_code == 200 and updated.json()["full_name"] == "QA profile"
    created = client.post(
        "/api/v1/auth/users",
        json={"username": "qa-user", "email": "qa-user@example.com", "password": "safe-password"},
        headers=headers,
    )
    assert created.status_code == 201
    uid = created.json()["user_id"]
    assert (
        client.patch(
            f"/api/v1/auth/users/{uid}", json={"full_name": "QA edited", "is_active": False}, headers=headers
        ).status_code
        == 200
    )
    login = client.post("/api/v1/auth/login", json={"username": "qa-user", "password": "safe-password"})
    assert login.status_code in {401, 403}
    assert client.delete(f"/api/v1/auth/users/{uid}", headers=headers).status_code == 200
    key = client.post("/api/v1/auth/apikeys", json={"name": "QA temporary", "expires_days": 1}, headers=headers)
    assert key.status_code == 201
    key_data = key.json()
    key_id = key_data["key_id"]
    assert client.get("/api/v1/auth/me", headers={"X-API-Key": key_data["api_key"]}).status_code == 200
    assert (
        client.put(
            f"/api/v1/auth/apikeys/{key_id}/webhook", json={"enabled": False, "url": ""}, headers=headers
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/auth/apikeys/{key_id}", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers={"X-API-Key": key_data["api_key"]}).status_code == 401
    assert me["user_id"]


def test_registration_password_change_and_logout(workbench):
    _, client, admin_headers = workbench
    assert client.post(
        "/api/v1/auth/system/config", json={"allow_registration": True}, headers=admin_headers
    ).status_code == 200
    credentials = {"username": "qa-registration", "password": "qa-old-password"}
    registered = client.post(
        "/api/v1/auth/register", json={**credentials, "email": "qa-registration@example.com"}
    )
    assert registered.status_code == 201
    assert registered.json()["role"] == "user"
    assert client.post(
        "/api/v1/auth/register", json={**credentials, "email": "qa-registration@example.com"}
    ).status_code == 400
    assert client.post(
        "/api/v1/auth/login", json={**credentials, "password": "wrong-password"}
    ).status_code == 401
    login = client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.post(
        "/api/v1/auth/me/change-password",
        json={"old_password": "wrong-password", "new_password": "qa-new-password"}, headers=headers
    ).status_code == 400
    assert client.post(
        "/api/v1/auth/me/change-password",
        json={"old_password": credentials["password"], "new_password": "qa-new-password"}, headers=headers
    ).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    login = client.post("/api/v1/auth/login", json={**credentials, "password": "qa-new-password"})
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_pause_resume_cancel_retry_cache_and_delete(workbench, runtime_paths):
    api, client, headers = workbench
    uploaded = client.post("/api/v1/tasks/submit", files={"file": ("qa.txt", b"QA content")}, headers=headers)
    assert uploaded.status_code == 200
    tid = uploaded.json()["task_id"]
    root = f"/api/v1/tasks/{tid}"
    assert client.post(root + "/pause", headers=headers).status_code == 200
    assert api.db.get_task(tid)["status"] == "paused"
    assert client.post(root + "/resume", headers=headers).status_code == 200
    assert api.db.get_task(tid)["status"] == "pending"
    assert client.post(root + "/clear-cache", headers=headers).status_code == 409
    assert client.post(root + "/retry", headers=headers).status_code == 409
    assert client.post(root + "/cancel", headers=headers).status_code == 200
    assert client.post(root + "/retry", headers=headers).status_code == 200
    assert api.db.get_task(tid)["status"] == "pending"
    output = runtime_paths["output_path"] / tid
    output.mkdir()
    (output / "result.md").write_text("QA result")
    api.db.get_next_task("qa-worker")
    api.db.update_task_status(tid, "completed", result_path=str(output))
    assert client.post(root + "/retry", headers=headers).status_code == 409
    assert (output / "result.md").is_file()
    assert client.post(root + "/clear-cache", headers=headers).status_code == 200
    assert not output.exists()
    assert client.get(root, headers=headers).json()["result_path"] == "CLEARED"
    assert client.delete(root, headers=headers).status_code == 200
    assert client.get(root, headers=headers).status_code == 404


@pytest.mark.parametrize("params", [{"start_page": -1}, {"start_page": 2, "end_page": 1}, {"method": "invalid"}])
def test_invalid_submit_options_create_no_task(workbench, params):
    api, client, headers = workbench
    response = client.post("/api/v1/tasks/submit", files={"file": ("qa.txt", b"QA")}, data=params, headers=headers)
    assert response.status_code == 400
    assert api.db.get_queue_stats().get("pending", 0) == 0


@pytest.mark.parametrize(
    "path", ["/admin/cleanup?days=0", "/admin/cleanup?days=-1", "/admin/reset-stale?timeout_minutes=0"]
)
def test_maintenance_rejects_dangerous_ranges(workbench, path):
    _, client, headers = workbench
    assert client.post("/api/v1" + path, headers=headers).status_code == 422


def test_settings_sections_audit_and_openapi(workbench):
    _, client, headers = workbench
    for path in [
        "/auth/system/config",
        "/auth/system/config/image-caption",
        "/auth/system/config/webhook",
        "/auth/system/config/task",
        "/auth/admin/apikeys",
        "/auth/system/webhook/deliveries",
        "/admin/audit-logs",
        "/queue/stats",
        "/engines",
        "/openapi.json",
    ]:
        response = client.get("/api/v1" + path, headers=headers)
        assert response.status_code == 200, (path, response.text)
    invalid = client.post(
        "/api/v1/auth/system/config/image-caption/test", json={"api_base": "", "model": ""}, headers=headers
    )
    assert invalid.status_code == 400
    for payload in [{"webhook_timeout": 11}, {"webhook_timeout": 10}, {"task_max_retries": 3}, {"task_max_retries": 2}]:
        assert client.post("/api/v1/auth/system/config", json=payload, headers=headers).status_code == 200


def test_non_admin_cannot_reach_administration(workbench, runtime_paths):
    _, client, _ = workbench
    headers = make_token(runtime_paths, UserRole.USER)
    for path in ["/auth/users", "/auth/admin/apikeys", "/admin/audit-logs", "/auth/system/config/task"]:
        assert client.get("/api/v1" + path, headers=headers).status_code == 403


def test_local_logo_upload_preview_and_validation(workbench, monkeypatch):
    import io
    from PIL import Image

    _, client, headers = workbench
    monkeypatch.setenv("RUSTFS_ENABLED", "false")
    image = io.BytesIO()
    Image.new("RGB", (20, 20), "blue").save(image, format="PNG")
    response = client.post(
        "/api/v1/auth/system/logo/upload", files={"file": ("logo.png", image.getvalue(), "image/png")}, headers=headers
    )
    assert response.status_code == 200
    url = response.json()["logo_url"]
    preview = client.get(url)
    assert preview.status_code == 200 and preview.headers["content-type"].startswith("image/png")
    assert client.get("/api/v1/auth/system/config").json()["config"]["system_logo"] == ""
    invalid = client.post(
        "/api/v1/auth/system/logo/upload", files={"file": ("fake.png", b"not a real image")}, headers=headers
    )
    assert invalid.status_code == 400
