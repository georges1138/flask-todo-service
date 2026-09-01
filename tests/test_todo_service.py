import pytest

from models import db
from models.user import User
from models.todo import Todo
from models.sync_job import SyncJob
from services.todo_service import TodoService


@pytest.fixture
def todo_scenario(app):
    user_a = User(
        username='alice',
        email='alice@example.com',
        password_hash='fake-hash-a'
    )

    user_b = User(
        username='bob',
        email='bob@example.com',
        password_hash='fake-hash-b'
    )

    db.session.add_all([user_a, user_b])
    db.session.commit()

    todo_a = Todo(
        title='Alice Todo',
        description="Alice's task",
        user_id=user_a.id
    )

    todo_b = Todo(
        title='Bob Todo',
        description="Bob's task",
        user_id=user_b.id
    )

    db.session.add_all([todo_a, todo_b])
    db.session.commit()

    return {
        'user_a': user_a,
        'user_b': user_b,
        'todo_a': todo_a,
        'todo_b': todo_b,
    }


def test_add_todo(app):
    user = User(
        username="alice",
        email="alice@example.com",
        password_hash="fake-hash",
    )

    db.session.add(user)
    db.session.commit()

    todo = TodoService.add(
        user.id,
        "Buy milk",
        "Get whole milk"
    )

    assert todo.title == "Buy milk"
    assert todo.description == "Get whole milk"
    assert todo.user_id == user.id
    assert todo.completed is False
    assert todo.completed_at is None
    assert todo.created_at is not None


def test_get_all_excludes_other_users(todo_scenario):
    user_a = todo_scenario["user_a"]
    todo_a = todo_scenario["todo_a"]
    todo_b = todo_scenario["todo_b"]

    todos = TodoService.get_all(user_a.id)

    todo_ids = [todo.todo_id for todo in todos]

    assert todo_a.todo_id in todo_ids
    assert todo_b.todo_id not in todo_ids


def test_get_by_id_returns_none_for_other_users_todo(todo_scenario):
    user_a = todo_scenario["user_a"]
    todo_b = todo_scenario["todo_b"]

    result = TodoService.get_by_id(
        user_a.id,
        todo_b.todo_id
    )

    assert result is None


def test_update_does_not_change_other_users_todo(todo_scenario):
    user_a = todo_scenario["user_a"]
    todo_b = todo_scenario["todo_b"]

    original_title = todo_b.title
    todo_b_id = todo_b.todo_id

    result = TodoService.update(
        user_a.id,
        todo_b_id,
        "Hacked title",
        "This should never be saved"
    )

    assert result is False

    db.session.expire_all()

    unchanged_todo = db.session.get(Todo, todo_b_id)

    assert unchanged_todo is not None
    assert unchanged_todo.title == original_title


def test_delete_does_not_remove_other_users_todo(todo_scenario):
    user_a = todo_scenario["user_a"]
    todo_b = todo_scenario["todo_b"]

    todo_b_id = todo_b.todo_id

    result = TodoService.delete(
        user_a.id,
        todo_b_id
    )

    assert result is False

    db.session.expire_all()

    existing_todo = db.session.get(Todo, todo_b_id)

    assert existing_todo is not None


def test_update_changes_owners_todo(todo_scenario):
    user_a = todo_scenario["user_a"]
    todo_a = todo_scenario["todo_a"]

    todo_a_id = todo_a.todo_id

    result = TodoService.update(
        user_a.id,
        todo_a_id,
        "Updated title",
        "Updated description"
    )

    assert result is True

    db.session.expire_all()

    updated_todo = db.session.get(Todo, todo_a_id)

    assert updated_todo is not None
    assert updated_todo.title == "Updated title"
    assert updated_todo.description == "Updated description"


def test_delete_removes_owners_todo(todo_scenario):
    user_a = todo_scenario["user_a"]
    todo_a = todo_scenario["todo_a"]

    todo_a_id = todo_a.todo_id

    result = TodoService.delete(
        user_a.id,
        todo_a_id
    )

    assert result is True

    db.session.expire_all()

    deleted_todo = db.session.get(Todo, todo_a_id)

    assert deleted_todo is None


def test_toggle_complete_marks_owners_todo_complete(todo_scenario):
    user_a = todo_scenario['user_a']
    todo_a = todo_scenario['todo_a']

    todo_a_id = todo_a.todo_id

    result = TodoService.toggle_complete(
        user_a.id,
        todo_a_id
    )

    assert result is True

    db.session.expire_all()

    updated_todo = db.session.get(Todo, todo_a_id)

    assert updated_todo is not None
    assert updated_todo.completed is True
    assert updated_todo.completed_at is not None

    filters = [SyncJob.source_todo_id == todo_a_id]
    stmt = (
        db.select(db.func.count())
        .select_from(SyncJob)
        .where(*filters)
    )
    assert db.session.scalar(stmt) == 1

    stmt = (
        db.select(SyncJob).where(*filters)
    )
    test_job = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert test_job.email_address == updated_todo.user.email
    assert test_job.source_todo_id == updated_todo.todo_id
    assert test_job.todo_title == updated_todo.title
    assert test_job.completed_at == updated_todo.completed_at


def test_toggle_complete_does_not_change_other_users_todo(todo_scenario):
    user_a = todo_scenario['user_a']
    todo_b = todo_scenario['todo_b']

    todo_b_id = todo_b.todo_id

    result = TodoService.toggle_complete(
        user_a.id,
        todo_b_id
    )

    assert result is False

    db.session.expire_all()

    unchanged_todo = db.session.get(Todo, todo_b_id)

    assert unchanged_todo is not None
    assert unchanged_todo.completed is False
    assert unchanged_todo.completed_at is None


def test_toggle_complete_twice_restores_incomplete_state(todo_scenario):
    user_a = todo_scenario["user_a"]
    todo_a = todo_scenario["todo_a"]

    todo_a_id = todo_a.todo_id

    first_result = TodoService.toggle_complete(
        user_a.id,
        todo_a_id
    )

    second_result = TodoService.toggle_complete(
        user_a.id,
        todo_a_id
    )

    assert first_result is True
    assert second_result is True

    db.session.expire_all()

    todo = db.session.get(Todo, todo_a_id)

    assert todo is not None
    assert todo.completed is False
    assert todo.completed_at is None

    filters = [SyncJob.source_todo_id == todo_a_id]
    stmt = (
        db.select(db.func.count())
        .select_from(SyncJob)
        .where(*filters)
    )
    assert db.session.scalar(stmt) == 1


def test_recompleted_todo_creates_new_sync_job(todo_scenario):
    user_a = todo_scenario["user_a"]
    todo_a = todo_scenario["todo_a"]
    todo_a_id = todo_a.todo_id

    # complete the Todo once
    TodoService.toggle_complete(
        user_a.id,
        todo_a_id,
    )
    # reopen it
    TodoService.toggle_complete(
        user_a.id,
        todo_a_id,
    )
    # complete it again
    TodoService.toggle_complete(
        user_a.id,
        todo_a_id,
    )
    stmt = db.select(SyncJob).where(
        SyncJob.source_todo_id == todo_a_id
    )
    rows = db.session.execute(
        stmt
    ).scalars().all()

    assert len(rows) == 2
    assert rows[0].idempotency_key != rows[1].idempotency_key
