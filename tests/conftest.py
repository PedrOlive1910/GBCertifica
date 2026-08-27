import pytest

from app import create_app
from app.extensions import db
from app.models import Tenant


@pytest.fixture()
def app():
    aplicacao = create_app("testing")

    with aplicacao.app_context():
        db.create_all()
        db.session.add(
            Tenant(
                id=aplicacao.config["TEST_TENANT_ID"],
                nome="Conta de Teste",
                slug="conta-teste",
            )
        )
        db.session.commit()
        yield aplicacao
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
