import pytest

from services.user_service import UserService
from services.token_service import TokenService
from services.todo_service import TodoService


@pytest.fixture
def authenticated_api_user(app):
    # Create a real user with a real password hash
    user = UserService.register(
        username="alice",
        email="alice@example.com",
        password="correct-password",
    )

    # Issue a real API token for that user
    raw_token, api_token = TokenService.issue_token(
        user.id,
        "pytest"
    )

    return {
        "user": user,
        "raw_token": raw_token,
        "api_token": api_token,
    }


def test_get_todos_requires_bearer_token(client):
    response = client.get(
        "/api/v1/todos"
    )
    assert response.status_code == 401
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Missing or malformed Authorization header"


def test_get_todos_returns_only_authenticated_users_todos(
    client,
    authenticated_api_user
):
    user = authenticated_api_user["user"]
    raw_token = authenticated_api_user["raw_token"]

    # Create two todos owned by our authenticated user
    TodoService.add(
        user.id,
        "Buy groceries",
        "Milk and bread"
    )

    TodoService.add(
        user.id,
        "Study Flask",
        "Work on REST API"
    )

    # Create another user
    other_user = UserService.register(
        username="bob",
        email="bob@example.com",
        password="another-password",
    )

    # Create a todo owned by the OTHER user
    TodoService.add(
        other_user.id,
        "Bob's private todo",
        "Alice should not see this"
    )

    # Build a real Bearer Authorization header
    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    # Test Todos test starts here
    response = client.get(
        "/api/v1/todos",
        headers=headers
    )

    assert response.status_code == 200

    assert response.is_json
    data = response.get_json()

    assert len(data) == 2

    titles = {todo['title'] for todo in data}

    assert "Buy groceries" in titles
    assert "Study Flask" in titles

    assert "Bob's private todo" not in titles

    for todo in data:
        assert "user_id" not in todo


def test_get_single_todo_returns_authenticated_users_todo(
    client,
    authenticated_api_user
):
    user = authenticated_api_user["user"]
    raw_token = authenticated_api_user["raw_token"]

    # Create one Todo owned by the authenticated user.
    todo = TodoService.add(
        user.id,
        "Read Flask docs",
        "Study route parameters"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.get(
        f"/api/v1/todos/{todo.todo_id}",
        headers=headers
    )

    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()

    assert data["todo_id"] == todo.todo_id
    assert data["title"] == todo.title
    assert data["description"] == todo.description

    assert data["completed"] is False

    # OPTIONAL:
    # Prove user_id is not exposed.
    assert "user_id" not in data


def test_get_single_todo_returns_404_for_missing_todo(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.get(
        "/api/v1/todos/999999",
        headers=headers
    )

    assert response.status_code == 404
    assert response.is_json

    data = response.get_json()

    assert data["error"] == "Todo not found"


def test_get_single_todo_does_not_expose_other_users_todo(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    # Create another user.
    other_user = UserService.register(
        username="bob",
        email="bob@example.com",
        password="another-password",
    )

    # Create a Todo belonging to Bob.
    other_todo = TodoService.add(
        other_user.id,
        "Bob's secret todo",
        "Alice must not see this"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    # Alice's Bearer token is being used here.
    response = client.get(
        f"/api/v1/todos/{other_todo.todo_id}",
        headers=headers
    )

    assert response.status_code == 404
    assert response.is_json
    data = response.get_json()

    assert data["error"] == "Todo not found"


def test_create_todo_creates_todo_for_authenticated_user(
    client,
    authenticated_api_user
):
    user = authenticated_api_user["user"]
    raw_token = authenticated_api_user["raw_token"]

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.post(
        "/api/v1/todos",
        headers=headers,
        json={
            "title": "Write API tests",
            "description": "Practice POST endpoint testing"
        }
    )

    assert response.status_code == 201
    assert response.is_json

    data = response.get_json()
    assert data["title"] == "Write API tests"
    assert data["description"] == "Practice POST endpoint testing"

    assert data["completed"] is False
    assert "todo_id" in data
    assert "user_id" not in data

    # Now verify the Todo really exists in the database.
    created_todo = TodoService.get_by_id(
        user.id,
        data["todo_id"]
    )

    assert created_todo is not None
    assert created_todo.user_id == user.id

    assert created_todo.title == data["title"]
    assert created_todo.description == data["description"]


def test_create_todo_rejects_missing_json(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.post(
        "/api/v1/todos",
        headers=headers
    )

    assert response.status_code == 400
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Invalid or missing JSON payload"


def test_create_todo_rejects_missing_required_fields(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.post(
        "/api/v1/todos",
        headers=headers,
        json={
            "title": "This has no description"
        }
    )

    assert response.status_code == 400
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Missing required fields: title or description"


def test_update_todo_updates_authenticated_users_todo(
    client,
    authenticated_api_user
):
    user = authenticated_api_user["user"]
    raw_token = authenticated_api_user["raw_token"]

    todo = TodoService.add(
        user.id,
        "Old title",
        "Old description"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.put(
        f"/api/v1/todos/{todo.todo_id}",
        headers=headers,
        json={
            "title": "Updated title",
            "description": "Updated description"
        }
    )

    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()
    assert data["todo_id"] == todo.todo_id
    assert data["title"] == "Updated title"
    assert data["description"] == "Updated description"
    assert "user_id" not in data

    # Now verify PostgreSQL actually contains the update.
    updated_todo = TodoService.get_by_id(
        user.id,
        todo.todo_id
    )

    assert updated_todo is not None
    assert updated_todo.todo_id == todo.todo_id
    assert updated_todo.title == "Updated title"
    assert updated_todo.description == "Updated description"


def test_update_todo_rejects_missing_json(
    client,
    authenticated_api_user
):
    user = authenticated_api_user["user"]
    raw_token = authenticated_api_user["raw_token"]

    todo = TodoService.add(
        user.id,
        "Original title",
        "Original description"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.put(
        f"/api/v1/todos/{todo.todo_id}",
        headers=headers
    )

    assert response.status_code == 400
    assert response.is_json
    data = response.get_json()

    assert data["error"] == "Invalid or missing JSON payload"


def test_update_todo_rejects_missing_required_fields(
    client,
    authenticated_api_user
):
    user = authenticated_api_user["user"]
    raw_token = authenticated_api_user["raw_token"]

    todo = TodoService.add(
        user.id,
        "Original title",
        "Original description"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.put(
        f"/api/v1/todos/{todo.todo_id}",
        headers=headers,
        json={
            "title": "New title"
        }
    )

    assert response.status_code == 400
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Missing required fields: title or description"


def test_update_todo_returns_404_for_missing_todo(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.put(
        "/api/v1/todos/999999",
        headers=headers,
        json={
            "title": "Does not matter",
            "description": "Todo does not exist"
        }
    )

    assert response.status_code == 404
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Todo not found"


def test_update_todo_does_not_update_other_users_todo(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    other_user = UserService.register(
        username="bob",
        email="bob@example.com",
        password="another-password",
    )

    other_todo = TodoService.add(
        other_user.id,
        "Bob's title",
        "Bob's description"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.put(
        f"/api/v1/todos/{other_todo.todo_id}",
        headers=headers,
        json={
            "title": "Alice tries to change this",
            "description": "This must not succeed"
        }
    )

    assert response.status_code == 404
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Todo not found"

    stored_todo = TodoService.get_by_id(
        other_user.id,
        other_todo.todo_id
    )

    assert stored_todo is not None
    assert stored_todo.todo_id == other_todo.todo_id
    assert stored_todo.title == "Bob's title"
    assert stored_todo.description == "Bob's description"


def test_delete_todo_deletes_authenticated_users_todo(
    client,
    authenticated_api_user
):
    user = authenticated_api_user["user"]
    raw_token = authenticated_api_user["raw_token"]

    todo = TodoService.add(
        user.id,
        "Delete me",
        "This Todo should disappear"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.delete(
        f"/api/v1/todos/{todo.todo_id}",
        headers=headers
    )
    assert response.status_code == 204
    assert response.data == b""

    deleted_todo = TodoService.get_by_id(
        user.id,
        todo.todo_id
    )
    assert deleted_todo is None


def test_delete_todo_returns_404_for_missing_todo(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.delete(
        "/api/v1/todos/999999",
        headers=headers
    )

    assert response.status_code == 404
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Todo not found"


def test_delete_todo_does_not_delete_other_users_todo(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    other_user = UserService.register(
        username="bob",
        email="bob@example.com",
        password="another-password",
    )

    other_todo = TodoService.add(
        other_user.id,
        "Bob's Todo",
        "Alice must not delete this"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.delete(
        f"/api/v1/todos/{other_todo.todo_id}",
        headers=headers
    )

    assert response.status_code == 404
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Todo not found"

    stored_todo = TodoService.get_by_id(
        other_user.id,
        other_todo.todo_id
    )

    assert stored_todo is not None
    assert stored_todo.todo_id == other_todo.todo_id
    assert stored_todo.user_id == other_user.id


def test_toggle_todo_completion_marks_todo_complete(
    client,
    authenticated_api_user
):
    user = authenticated_api_user["user"]
    raw_token = authenticated_api_user["raw_token"]

    todo = TodoService.add(
        user.id,
        "Finish API",
        "Complete the PATCH endpoint"
    )

    # Sanity check our starting state.
    assert todo.completed is False
    assert todo.completed_at is None

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.patch(
        f"/api/v1/todos/{todo.todo_id}/completion",
        headers=headers
    )

    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()

    assert data["todo_id"] == todo.todo_id
    assert data["completed"] is True
    assert data["completed_at"] is not None
    assert "user_id" not in data

    stored_todo = TodoService.get_by_id(
        user.id,
        todo.todo_id
    )

    assert stored_todo is not None
    assert stored_todo.todo_id == todo.todo_id
    assert stored_todo.completed is True
    assert stored_todo.completed_at is not None


def test_toggle_todo_completion_twice_restores_incomplete_state(
    client,
    authenticated_api_user
):
    user = authenticated_api_user["user"]
    raw_token = authenticated_api_user["raw_token"]

    todo = TodoService.add(
        user.id,
        "Toggle twice",
        "Should end where it started"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    # First PATCH: incomplete -> complete
    first_response = client.patch(
        f"/api/v1/todos/{todo.todo_id}/completion",
        headers=headers
    )

    assert first_response.status_code == 200
    first_data = first_response.get_json()
    assert first_data["completed"] is True

    # Second PATCH: complete -> incomplete
    second_response = client.patch(
        f"/api/v1/todos/{todo.todo_id}/completion",
        headers=headers
    )

    assert second_response.status_code == 200
    second_data = second_response.get_json()
    assert second_data["completed"] is False
    assert second_data["completed_at"] is None

    stored_todo = TodoService.get_by_id(
        user.id,
        todo.todo_id
    )

    assert stored_todo is not None
    assert stored_todo.completed is False
    assert stored_todo.completed_at is None


def test_toggle_todo_completion_returns_404_for_missing_todo(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    response = client.patch(
        "/api/v1/todos/999999/completion",
        headers=headers
    )

    assert response.status_code == 404
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Todo not found"


def test_toggle_todo_completion_does_not_change_other_users_todo(
    client,
    authenticated_api_user
):
    raw_token = authenticated_api_user["raw_token"]

    other_user = UserService.register(
        username="bob",
        email="bob@example.com",
        password="another-password",
    )

    other_todo = TodoService.add(
        other_user.id,
        "Bob's Todo",
        "Alice must not toggle this"
    )

    headers = {
        "Authorization": f"Bearer {raw_token}"
    }

    # Alice's token attempts to toggle Bob's Todo.
    response = client.patch(
        f"/api/v1/todos/{other_todo.todo_id}/completion",
        headers=headers
    )

    assert response.status_code == 404
    assert response.is_json

    data = response.get_json()
    assert data["error"] == "Todo not found"

    stored_todo = TodoService.get_by_id(
        other_user.id,
        other_todo.todo_id
    )

    assert stored_todo is not None
    assert stored_todo.completed is False
    assert stored_todo.completed_at is None
