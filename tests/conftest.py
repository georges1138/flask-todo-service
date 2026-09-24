import os
import pytest

from app import create_app
from flask_sqlalchemy.session import Session as FlaskSession
from models import db, Todo, ApiToken, SyncJob, User


class TestSession(FlaskSession):

    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        if bind is not None:
            return bind

        if self.bind is not None:
            return self.bind

        return super().get_bind(
            mapper=mapper,
            clause=clause,
            bind=bind,
            **kwargs
        )


@pytest.fixture(scope="session")
def flask_app():
    test_database_url = os.environ.get("TEST_DATABASE_URL")

    if not test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL environment variable is required"
        )

    flask_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": test_database_url,
        "SECRET_KEY": "test-secret",
    })

    return flask_app


@pytest.fixture(scope="session")
def database_schema(flask_app):
    with flask_app.app_context():
        if db.engine.url.database != "todo_test":
            raise RuntimeError("Refusing cleanup: database is not todo_test")

        db.create_all()

        yield flask_app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def test_transaction(flask_app, database_schema):

    with flask_app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()

        db.session.registry.set(
            TestSession(
                db=db,
                bind=connection,
                join_transaction_mode="create_savepoint",
            )
        )

        yield connection

        db.session.remove()

        transaction.rollback()
        connection.close()


@pytest.fixture
def app(flask_app, test_transaction):
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def committed_data_context(flask_app, database_schema):
    with flask_app.app_context():
        yield clear_committed_test_data

        db.session.remove()
        try:
            clear_committed_test_data()
        finally:
            db.session.remove()


def clear_committed_test_data():
    if db.engine.url.database != "todo_test":
        raise RuntimeError("Refusing cleanup: database is not todo_test")

    db.session.execute(db.delete(Todo))

    db.session.execute(db.delete(ApiToken))

    db.session.execute(db.delete(SyncJob))

    db.session.execute(db.delete(User))

    db.session.commit()
