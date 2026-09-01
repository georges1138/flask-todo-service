import pytest

from datetime import datetime, timezone, date
from decimal import Decimal
from models import db
from models.user import User
from models.todo import Todo
from services.reporting_service import ReportingService


@pytest.fixture
def reporting_scenario(app):
    user_a = User(
        username='alice',
        email='alice@example.com',
        password_hash='fake-hash-a',
    )

    user_b = User(
        username='bob',
        email='bob@example.com',
        password_hash='fake-hash-b',
    )

    db.session.add_all([user_a, user_b])
    db.session.commit()

    # (title, description, completed, created_at, completed_at)
    alice_todo_data = [
        ('Alice task 1', 'Task 1 alice', False, datetime(2026, 7, 20, 11, 0, tzinfo=timezone.utc), None),
        ('Alice task 2', 'Task 2 alice', False, datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc), None),
        ('Alice task 3', 'Task 3 alice', True, datetime(2026, 7, 28, 10, 30, tzinfo=timezone.utc),
         datetime(2026, 7, 30, 14, 00, tzinfo=timezone.utc)),
        ('Alice task 4', 'Task 4 alice', False, datetime(2026, 7, 30, 11, 30, tzinfo=timezone.utc), None),
        ('Alice task 5', 'Task 5 alice', True, datetime(2026, 8, 4, 11, 35, tzinfo=timezone.utc),
         datetime(2026, 8, 7, 14, 00, tzinfo=timezone.utc)),
        ('Alice task 6', 'Task 6 alice', True, datetime(2026, 8, 5, 8, 35, tzinfo=timezone.utc),
         datetime(2026, 8, 11, 13, 00, tzinfo=timezone.utc)),
        ('Alice task 7', 'Task 7 alice', False, datetime(2026, 8, 7, 13, 35, tzinfo=timezone.utc), None),
        ('Alice task 8', 'Task 8 alice', True, datetime(2026, 8, 10, 8, 42, tzinfo=timezone.utc),
         datetime(2026, 8, 12, 11, 45, tzinfo=timezone.utc)),
    ]

    # (title, description, completed, created_at, completed_at)
    bob_todo_data = [
        ('Bob task 1', 'Task 1 bob', True, datetime(2026, 7, 13, 8, 42, tzinfo=timezone.utc),
         datetime(2026, 7, 29, 11, 45, tzinfo=timezone.utc)),
        ('Bob task 2', 'Task 2 bob', True, datetime(2026, 7, 15, 8, 42, tzinfo=timezone.utc),
         datetime(2026, 7, 20, 12, 45, tzinfo=timezone.utc)),
        ('Bob task 3', 'Task 3 bob', True, datetime(2026, 7, 21, 8, 42, tzinfo=timezone.utc),
         datetime(2026, 7, 23, 12, 45, tzinfo=timezone.utc)),
        ('Bob task 4', 'Task 4 bob', True, datetime(2026, 7, 22, 8, 42, tzinfo=timezone.utc),
         datetime(2026, 7, 24, 12, 45, tzinfo=timezone.utc)),
        ('Bob task 5', 'Task 5 bob', False, datetime(2026, 7, 23, 9, 36, tzinfo=timezone.utc), None),
        ('Bob task 6', 'Task 6 bob', False, datetime(2026, 7, 29, 9, 36, tzinfo=timezone.utc), None),
        ('Bob task 7', 'Task 7 bob', False, datetime(2026, 7, 30, 14, 36, tzinfo=timezone.utc), None),
        ('Bob task 8', 'Task 8 bob', False, datetime(2026, 7, 31, 15, 36, tzinfo=timezone.utc), None),
        ('Bob task 9', 'Task 9 bob', False, datetime(2026, 8, 4, 15, 36, tzinfo=timezone.utc), None),
        ('Bob task 10', 'Task 10 bob', True, datetime(2026, 8, 6, 9, 48, tzinfo=timezone.utc),
         datetime(2026, 8, 11, 12, 45, tzinfo=timezone.utc)),
        ('Bob task 11', 'Task 11 bob', True, datetime(2026, 8, 10, 9, 48, tzinfo=timezone.utc),
         datetime(2026, 8, 11, 13, 45, tzinfo=timezone.utc)),
    ]

    todos_to_add = []

    for title, desc, completed, created_at, completed_at in alice_todo_data:
        todos_to_add.append(
            Todo(
                title=title,
                description=desc,
                completed=completed,
                created_at=created_at,
                completed_at=completed_at,
                user_id=user_a.id
            )
        )

    for title, desc, completed, created_at, completed_at in bob_todo_data:
        todos_to_add.append(
            Todo(
                title=title,
                description=desc,
                completed=completed,
                created_at=created_at,
                completed_at=completed_at,
                user_id=user_b.id
            )
        )

    db.session.add_all(todos_to_add)
    db.session.commit()

    return {
        'user_a': user_a,
        'user_b': user_b,
    }


def test_get_completion_rates_for_alice(reporting_scenario):
    alice = reporting_scenario["user_a"]

    rows = ReportingService.get_completion_rates()

    alice_rows = [row for row in rows if row.user_id == alice.id]

    assert len(alice_rows) == 4

    first_week = alice_rows[0]

    assert first_week.week_buck == date(2026, 7, 20)
    assert first_week.total_todos == 2
    assert first_week.completed_todos == 0


def test_alice_weekly_buckets(reporting_scenario):
    alice = reporting_scenario["user_a"]
    rows = ReportingService.get_completion_rates()
    alice_rows = [row for row in rows if row.user_id == alice.id]

    expected_weeks = [
        date(2026, 7, 20),
        date(2026, 7, 27),
        date(2026, 8, 3),
        date(2026, 8, 10)
    ]

    assert len(alice_rows) == 4
    for i, row in enumerate(alice_rows):
        assert row.week_buck == expected_weeks[i], f"Mismatch at row {i}"


def test_alice_cumulative_progression(reporting_scenario):
    alice = reporting_scenario["user_a"]
    rows = ReportingService.get_completion_rates()
    alice_rows = [row for row in rows if row.user_id == alice.id]

    assert alice_rows[0].cumulative_total == 2
    assert alice_rows[0].cumulative_completed == 0

    assert alice_rows[1].cumulative_total == 4
    assert alice_rows[1].cumulative_completed == 1

    assert alice_rows[2].cumulative_total == 7
    assert alice_rows[2].cumulative_completed == 3

    assert alice_rows[3].cumulative_total == 8
    assert alice_rows[3].cumulative_completed == 4


def test_alice_completion_rates(reporting_scenario):
    alice = reporting_scenario["user_a"]
    rows = ReportingService.get_completion_rates()
    alice_rows = [row for row in rows if row.user_id == alice.id]

    expected_rates = [
        Decimal("0.00"),
        Decimal("25.00"),
        Decimal("42.86"),
        Decimal("50.00"),
    ]

    actual_rates = [
        row.cumulative_completion_rate
        for row in alice_rows
    ]

    assert actual_rates == expected_rates


def test_bob_cumulative_progression(reporting_scenario):
    bob = reporting_scenario["user_b"]
    rows = ReportingService.get_completion_rates()
    bob_rows = [row for row in rows if row.user_id == bob.id]

    assert len(bob_rows) == 5

    assert bob_rows[0].cumulative_total == 2
    assert bob_rows[0].cumulative_completed == 2

    assert bob_rows[1].cumulative_total == 5
    assert bob_rows[1].cumulative_completed == 4

    assert bob_rows[2].cumulative_total == 8
    assert bob_rows[2].cumulative_completed == 4

    assert bob_rows[3].cumulative_total == 10
    assert bob_rows[3].cumulative_completed == 5

    assert bob_rows[4].cumulative_total == 11
    assert bob_rows[4].cumulative_completed == 6


def test_user_partitions_are_independent(reporting_scenario):
    alice = reporting_scenario["user_a"]
    bob = reporting_scenario["user_b"]

    rows = ReportingService.get_completion_rates()
    alice_rows = [row for row in rows if row.user_id == alice.id]
    bob_rows = [row for row in rows if row.user_id == bob.id]

    bob_week_1 = bob_rows[0]
    alice_week_1 = alice_rows[0]

    assert bob_week_1.cumulative_total == bob_week_1.total_todos == 2
    assert bob_week_1.cumulative_completed == bob_week_1.completed_todos == 2

    assert alice_week_1.cumulative_total == alice_week_1.total_todos == 2
    assert alice_week_1.cumulative_completed == alice_week_1.completed_todos == 0


def test_completion_rates_can_be_scoped_to_user(reporting_scenario):
    alice = reporting_scenario["user_a"]

    rows = ReportingService.get_completion_rates(user_id=alice.id)

    assert len(rows) == 4
    assert all(row.user_id == alice.id for row in rows)


def test_completion_rates_for_unknown_user_returns_empty(reporting_scenario):
    rows = ReportingService.get_completion_rates(user_id=999)

    assert rows == []
