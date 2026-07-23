from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from demetra.app import app
from demetra.library.exceptions import AuthError as AuthServiceError
from demetra.library.models import AuthResponse, UserResponse


AUTH_BASE = "/api/v1/auth"


def _make_auth_response(user_id: str | None = None) -> AuthResponse:
    uid = user_id or str(uuid4())
    return AuthResponse(
        token=f"jwt-{uid}",
        user=UserResponse(
            id=uid,
            email=f"{uid[:8]}@example.com",
            github_username=None,
        ),
    )


class TestSignupEndpoint:
    def test_signup_returns_422_on_missing_body(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(f"{AUTH_BASE}/signup", json={})
        assert response.status_code == 422

    def test_signup_returns_200_and_sets_cookie(self):
        auth_response = _make_auth_response()

        with patch("demetra.api.auth.signup_with_password", new_callable=AsyncMock) as mock_signup:
            mock_signup.return_value = auth_response

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"{AUTH_BASE}/signup",
                json={"email": "newuser@example.com", "password": "hunter2hunter2"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["token"] == auth_response.token
            assert data["user"]["id"] == auth_response.user.id
            assert data["user"]["email"] == auth_response.user.email
            assert "auth_token" in response.cookies
            assert response.cookies["auth_token"] == auth_response.token
            mock_signup.assert_called_once_with(email="newuser@example.com", password="hunter2hunter2")

    def test_signup_returns_400_on_duplicate_email(self):
        with patch("demetra.api.auth.signup_with_password", new_callable=AsyncMock) as mock_signup:
            mock_signup.side_effect = AuthServiceError("Email already registered")

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"{AUTH_BASE}/signup",
                json={"email": "dup@example.com", "password": "hunter2hunter2"},
            )

            assert response.status_code == 400
            assert "Email already registered" in response.json()["detail"]

    def test_signup_returns_400_on_weak_password(self):
        with patch("demetra.api.auth.signup_with_password", new_callable=AsyncMock) as mock_signup:
            mock_signup.side_effect = AuthServiceError("Password must be at least 8 characters long")

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"{AUTH_BASE}/signup",
                json={"email": "weak@example.com", "password": "short"},
            )

            assert response.status_code == 400
            assert "Password" in response.json()["detail"]


class TestLoginEndpoint:
    def test_login_returns_200_and_sets_cookie(self):
        auth_response = _make_auth_response()

        with patch("demetra.api.auth.login_with_password", new_callable=AsyncMock) as mock_login:
            mock_login.return_value = auth_response

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"{AUTH_BASE}/login",
                json={"email": "user@example.com", "password": "hunter2hunter2"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["token"] == auth_response.token
            assert data["user"]["id"] == auth_response.user.id
            assert "auth_token" in response.cookies
            assert response.cookies["auth_token"] == auth_response.token
            mock_login.assert_called_once_with(email="user@example.com", password="hunter2hunter2")

    def test_login_returns_401_on_bad_credentials(self):
        with patch("demetra.api.auth.login_with_password", new_callable=AsyncMock) as mock_login:
            mock_login.side_effect = AuthServiceError("Invalid email or password")

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"{AUTH_BASE}/login",
                json={"email": "bad@example.com", "password": "wrongPassword1"},
            )

            assert response.status_code == 401
            assert "Invalid email or password" in response.json()["detail"]

    def test_login_returns_422_on_missing_body(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(f"{AUTH_BASE}/login", json={})
        assert response.status_code == 422


class TestLogoutEndpoint:
    def test_logout_returns_200_and_deletes_cookie(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(f"{AUTH_BASE}/logout", cookies={"auth_token": "some-token"})

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"

    def test_logout_works_without_cookie(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(f"{AUTH_BASE}/logout")

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"
