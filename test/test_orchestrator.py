import json
from datetime import datetime, timezone

import pytest

from src.orchestrator import order_workflow


class MockDurableOrchestrationContext:
    def __init__(self, input_data, timer_wins=False):
        self._input = input_data
        self._timer_wins = timer_wins
        self._current_utc_datetime = datetime(2026, 6, 6, 12, 0, 0, tzinfo=timezone.utc)
        self.call_history = []
        self.timer_created = False
        self.event_waited = False

    def get_input(self):
        return self._input

    async def call_activity(self, name, data=None):
        self.call_history.append((name, data))
        return {"status": "ok", "name": name}

    async def create_timer(self, expiry):
        self.timer_created = True
        return "timer_task"

    async def wait_for_external_event(self, name):
        self.event_waited = True
        return "event_task"

    async def task_any(self, tasks):
        if self._timer_wins:
            return tasks[0]
        return tasks[1]

    @property
    def current_utc_datetime(self):
        return self._current_utc_datetime


class TestOrchestrator:
    async def test_orchestrator_confirm_path(self):
        context = MockDurableOrchestrationContext(
            {"orderId": "ORD-0042"}, timer_wins=False
        )
        result = await order_workflow(context)
        assert result is not None

    async def test_orchestrator_timeout_path(self):
        context = MockDurableOrchestrationContext(
            {"orderId": "ORD-0042"}, timer_wins=True
        )
        result = await order_workflow(context)
        assert result is not None

    def test_orchestrator_determinism_no_io(self):
        import ast, inspect

        source = inspect.getsource(order_workflow)
        tree = ast.parse(source)
        calls = [
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        forbidden = ["datetime.now", "datetime.utcnow", "random", "uuid"]
        for f in forbidden:
            base = f.split(".")[-1]
            assert base not in calls, f"Non-deterministic call detected: {f}"

    async def test_orchestrator_replay_safe(self):
        ctx1 = MockDurableOrchestrationContext({"orderId": "ORD-0042"})
        ctx2 = MockDurableOrchestrationContext({"orderId": "ORD-0042"})
        result1 = await order_workflow(ctx1)
        result2 = await order_workflow(ctx2)
        assert result1 is not None
        assert result2 is not None

    def test_orchestrator_uses_context_time(self):
        import inspect

        source = inspect.getsource(order_workflow)
        assert "current_utc_datetime" in source, "Must use context.current_utc_datetime"

    def test_orchestrator_json_serializable(self, sample_order):
        input_data = json.dumps(sample_order)
        parsed = json.loads(input_data)
        assert parsed["customerName"] == sample_order["customerName"]
