"""TDD tests for auth: signup, login, refresh, logout, token protection."""


# --- Signup ---


def test_signup_success(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "user@example.com",
            "password": "StrongPass1!",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "user@example.com"
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


def test_signup_duplicate_email(client):
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "dup@example.com",
            "password": "StrongPass1!",
        },
    )
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "dup@example.com",
            "password": "StrongPass1!",
        },
    )
    assert resp.status_code == 409


def test_signup_weak_password(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "user@example.com",
            "password": "short",
        },
    )
    assert resp.status_code == 422


# --- Login ---


def test_login_success(client):
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "login@example.com",
            "password": "StrongPass1!",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "StrongPass1!",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "user@example.com",
            "password": "StrongPass1!",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "user@example.com",
            "password": "WrongPass1!",
        },
    )
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ghost@example.com",
            "password": "StrongPass1!",
        },
    )
    assert resp.status_code == 401


# --- Token protection ---


def test_protected_route_without_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_protected_route_with_valid_token(client):
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "me@example.com",
            "password": "StrongPass1!",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "me@example.com",
            "password": "StrongPass1!",
        },
    )
    token = login.json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


def test_protected_route_with_invalid_token(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


# --- Refresh ---


def test_refresh_returns_new_tokens(client):
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "ref@example.com",
            "password": "StrongPass1!",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ref@example.com",
            "password": "StrongPass1!",
        },
    )
    refresh_token = login.json()["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    # New refresh token should differ (rotation)
    assert body["refresh_token"] != refresh_token


def test_refresh_old_token_rejected_after_rotation(client):
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "rot@example.com",
            "password": "StrongPass1!",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "rot@example.com",
            "password": "StrongPass1!",
        },
    )
    old_refresh = login.json()["refresh_token"]
    # Rotate
    client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    # Old token should be rejected
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401


# --- Logout ---


def test_logout_revokes_refresh_token(client):
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "out@example.com",
            "password": "StrongPass1!",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "out@example.com",
            "password": "StrongPass1!",
        },
    )
    tokens = login.json()
    resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    # Refresh should fail now
    resp = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": tokens["refresh_token"],
        },
    )
    assert resp.status_code == 401
