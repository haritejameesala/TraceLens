import asyncio
from types import SimpleNamespace

import pytest

from app import auth


class FakeUsers:
    def __init__(self):
        self.records = []

    async def find_one(self, query, projection=None):
        for record in self.records:
            matches = all(
                record.get(key) is not None if isinstance(value, dict) and value.get("$exists")
                else record.get(key) == value
                for key, value in query.items()
            )
            if matches:
                return record
        return None

    async def insert_one(self, record):
        self.records.append(dict(record))

    async def update_one(self, query, update):
        record = await self.find_one(query)
        if record:
            record.update(update["$set"])


class FakeCursor:
    def __init__(self, records):
        self.records = records

    def sort(self, *_args):
        return self

    def __aiter__(self):
        self._iterator = iter(self.records)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self, records=(), count=0):
        self.records = list(records)
        self.count = count

    def find(self, _query, projection):
        fields = {key for key, include in projection.items() if include}
        return FakeCursor([
            {key: value for key, value in record.items() if key in fields}
            for record in self.records
        ])

    async def count_documents(self, _query):
        return self.count


def test_password_hash_is_salted_and_verified():
    first = auth.hash_password("correct horse battery staple")
    second = auth.hash_password("correct horse battery staple")

    assert first != second
    assert auth.verify_password("correct horse battery staple", first)
    assert not auth.verify_password("wrong password", first)
    assert not auth.verify_password("anything", "not-a-valid-hash")


def test_signup_stores_only_password_hash_and_starts_session(monkeypatch):
    users = FakeUsers()
    monkeypatch.setattr(auth.db, "users", users)
    monkeypatch.setattr(auth.settings, "auth_mode", "accounts")
    request = SimpleNamespace(session={})
    body = auth.SignupRequest(
        name="Trace User",
        email="  USER@example.com ",
        password="a sufficiently long password",
    )

    result = asyncio.run(auth.signup(body, request))

    assert result["authenticated"] is True
    assert result["user"]["email"] == "user@example.com"
    assert request.session["user"]["user_id"] == result["user"]["user_id"]
    assert users.records[0]["email"] == "user@example.com"
    assert users.records[0]["password_hash"] != body.password
    assert "password" not in result["user"]


def test_login_uses_generic_error_for_unknown_email(monkeypatch):
    monkeypatch.setattr(auth.db, "users", FakeUsers())
    monkeypatch.setattr(auth.settings, "auth_mode", "accounts")

    with pytest.raises(auth.HTTPException) as error:
        asyncio.run(
            auth.account_login(
                auth.LoginRequest(email="unknown@example.com", password="not-the-password"),
                SimpleNamespace(session={}),
            )
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Email or password is incorrect"


def test_login_starts_a_session_for_valid_credentials(monkeypatch):
    password = "correct horse battery staple"
    users = FakeUsers()
    users.records.append({
        "user_id": "usr_test",
        "name": "Trace User",
        "email": "user@example.com",
        "password_hash": auth.hash_password(password),
        "provider": "password",
    })
    monkeypatch.setattr(auth, "db", SimpleNamespace(users=users))
    monkeypatch.setattr(auth.settings, "auth_mode", "accounts")
    request = SimpleNamespace(session={})

    result = asyncio.run(
        auth.account_login(
            auth.LoginRequest(email="USER@example.com", password=password),
            request,
        )
    )

    assert result["authenticated"] is True
    assert result["user"]["user_id"] == "usr_test"
    assert request.session["user"]["email"] == "user@example.com"


def test_signup_requires_a_long_password():
    with pytest.raises(ValueError):
        auth.SignupRequest(name="User", email="user@example.com", password="short")


def test_admin_role_requires_verified_allowlisted_email(monkeypatch):
    monkeypatch.setattr(auth.settings, "admin_emails", "admin@example.com, other@example.com")

    assert auth.is_admin_identity({
        "email": "ADMIN@example.com",
        "email_verified": True,
        "role": "user",
    })
    assert not auth.is_admin_identity({
        "email": "admin@example.com",
        "email_verified": False,
    })
    assert not auth.is_admin_identity({
        "email": "regular@example.com",
        "email_verified": True,
        "role": "admin",
    })


def test_admin_overview_rejects_non_admin_session(monkeypatch):
    from app import main

    monkeypatch.setattr(auth.settings, "admin_emails", "admin@example.com")
    request = SimpleNamespace(session={"user": {
        "user_id": "usr_regular",
        "email": "regular@example.com",
        "email_verified": True,
        "role": "admin",
    }})

    with pytest.raises(auth.HTTPException) as error:
        asyncio.run(main.admin_overview(request))

    assert error.value.status_code == 403


def test_admin_overview_lists_users_and_projects_without_password_hashes(monkeypatch):
    from app import main

    users = FakeCollection([{
        "user_id": "usr_admin",
        "name": "Admin",
        "email": "admin@example.com",
        "email_verified": True,
        "password_hash": "must-not-be-returned",
    }])
    projects = FakeCollection([{
        "project_id": "prj_user",
        "owner_user_id": "usr_admin",
        "name": "Support",
        "framework": "langchain",
    }])
    monkeypatch.setattr(main, "db", SimpleNamespace(
        users=users,
        projects=projects,
        runs=SimpleNamespace(count_documents=lambda _query: asyncio.sleep(0, result=3)),
    ))
    monkeypatch.setattr(auth.settings, "admin_emails", "admin@example.com")
    request = SimpleNamespace(session={"user": {
        "user_id": "usr_admin",
        "email": "admin@example.com",
        "email_verified": True,
    }})

    result = asyncio.run(main.admin_overview(request))

    assert result["user_count"] == 1
    assert result["project_count"] == 1
    assert result["run_count"] == 3
    assert result["projects"][0]["owner_email"] == "admin@example.com"
    assert "password_hash" not in result["users"][0]
