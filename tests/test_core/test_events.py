import pytest
from datetime import datetime
from src.core.events import EventSystem, EventType, Event


class TestEventSystem:
    def test_subscribe_and_publish(self):
        events = EventSystem()
        received = []

        def handler(event):
            received.append(event)

        events.subscribe(EventType.TEST_STARTED, handler)
        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert len(received) == 1
        assert received[0].type == EventType.TEST_STARTED

    def test_multiple_handlers(self):
        events = EventSystem()
        count = [0]

        def handler1(event):
            count[0] += 1

        def handler2(event):
            count[0] += 1

        events.subscribe(EventType.TEST_STARTED, handler1)
        events.subscribe(EventType.TEST_STARTED, handler2)
        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert count[0] == 2

    def test_unsubscribe(self):
        events = EventSystem()
        received = []

        def handler(event):
            received.append(event)

        events.subscribe(EventType.TEST_STARTED, handler)
        events.unsubscribe(EventType.TEST_STARTED, handler)
        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert len(received) == 0

    def test_different_event_types(self):
        events = EventSystem()
        started = []
        completed = []

        events.subscribe(EventType.TEST_STARTED, lambda e: started.append(e))
        events.subscribe(EventType.TEST_COMPLETED, lambda e: completed.append(e))

        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert len(started) == 1
        assert len(completed) == 0

    def test_event_data(self):
        events = EventSystem()
        received_data = {}

        def handler(event):
            received_data.update(event.data)

        events.subscribe(EventType.PROGRESS_UPDATE, handler)
        events.publish(Event(
            EventType.PROGRESS_UPDATE,
            datetime.now(),
            "engine",
            {"percentage": 50.0, "completed": 10}
        ))

        assert received_data["percentage"] == 50.0
        assert received_data["completed"] == 10

    def test_clear_handlers(self):
        events = EventSystem()
        received = []

        events.subscribe(EventType.TEST_STARTED, lambda e: received.append(e))
        events.clear_handlers()
        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert len(received) == 0
