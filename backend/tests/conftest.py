import os
import tempfile
from pathlib import Path
import pytest

_temp = tempfile.TemporaryDirectory(prefix='impact-tests-')
test_url = os.environ.get('IMPACT_TEST_DATABASE_URL', 'sqlite:///' + (Path(_temp.name) / 'test.db').as_posix())
if not test_url.startswith('sqlite:') and '/impact_test?' not in test_url and not test_url.endswith('/impact_test'):
    raise RuntimeError('Tests may only reset the dedicated impact_test database')
os.environ['DATABASE_URL'] = test_url
os.environ['SECRET_KEY'] = 'test-secret-only-do-not-use-outside-tests-123456789'
os.environ['STORAGE_DIR'] = str(Path(_temp.name) / 'materials')
os.environ['EVALUATION_ADAPTER'] = 'mock'

from fastapi.testclient import TestClient
from app.db import Base, engine, Session
from app.models import User
from app.auth import hash_password
from app.main import app


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _temp.cleanup()


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session() as db:
        db.add(User(username='admin', password_hash=hash_password('test-admin-password'), role='admin'))
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def admin_client():
    with TestClient(app) as client:
        response = client.post('/api/auth/login', json={'username': 'admin', 'password': 'test-admin-password'})
        assert response.status_code == 200
        yield client
