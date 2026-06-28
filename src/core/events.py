from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Any, Callable
from datetime import datetime


class EventType(str, Enum):
    """Types of events that can be published."""
    TEST_STARTED = "test_started"
    TEST_COMPLETED = "test_completed"
    TEST_FAILED = "test_failed"
    PROGRESS_UPDATE = "progress_update"
    DETECTOR_STARTED = "detector_started"
    DETECTOR_COMPLETED = "detector_completed"
    DETECTOR_FAILED = "detector_failed"
    ALL_TESTS_COMPLETED = "all_tests_completed"


@dataclass
class Event:
    """An event in the system."""
    type: EventType
    timestamp: datetime
    source: str
    data: Dict[str, Any]


class EventSystem:
    """Pub-sub event system for test progress notifications."""

    def __init__(self):
        self._handlers: Dict[EventType, List[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Unsubscribe from events."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # Handler errors should not affect other handlers
                pass

    def clear_handlers(self) -> None:
        """Clear all event handlers."""
        self._handlers.clear()
