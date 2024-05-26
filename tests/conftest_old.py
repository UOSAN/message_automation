import pytest
from src.flask_app import create_app


@pytest.fixture
def app():
    app = create_app(test_config={
        'TESTING': True
    })

    yield app
