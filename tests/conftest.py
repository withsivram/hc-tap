import pytest
from fastapi.testclient import TestClient

from services.api.app import app


@pytest.fixture
def api_client():
    return TestClient(app)


@pytest.fixture
def sample_text():
    return "Patient has diabetes and is taking metformin 500mg."
