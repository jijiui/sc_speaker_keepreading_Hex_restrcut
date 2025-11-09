"""Unit tests for TimelineService using the src/ layout."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.core.domain import TimelineEvent
from app.core.services.timeline_service import TimelineService


class TimelineServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TimelineService(global_lead_ms=2000)
        flows = {
            "PvZ": [
                TimelineEvent(time_ms=1000, action="一水晶"),
                TimelineEvent(time_ms=3000, action="网关"),
                TimelineEvent(time_ms=5000, action="折跃门"),
            ]
        }
        self.service.set_flows(flows)
        self.service.set_current_flow("PvZ")

    def test_advance_triggers_on_time(self) -> None:
        self.service.start()
        decision = self.service.advance(1000)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.event.action, "一水晶")
        self.assertEqual(decision.kind, "on_time")
        self.assertEqual(self.service.elapsed_ms, 1000)

    def test_no_announcement_when_not_running(self) -> None:
        decision = self.service.advance(2000)
        self.assertIsNone(decision)
        self.assertEqual(self.service.elapsed_ms, 0)

    def test_early_announcement_respects_lead(self) -> None:
        service = TimelineService(global_lead_ms=2000)
        service.set_flows({"Solo": [TimelineEvent(time_ms=3000, action="冲锋")]})
        service.set_current_flow("Solo")
        service.early_enabled = True
        service.start()
        decision = service.advance(1500)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.kind, "early")
        self.assertEqual(decision.event.action, "冲锋")

    def test_sync_elapsed_triggers_on_time(self) -> None:
        self.service.start()
        decision = self.service.sync_elapsed(3000)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.event.action, "一水晶")
        self.assertEqual(decision.kind, "on_time")

    def test_next_event_index(self) -> None:
        self.service.start()
        self.service.advance(2500)
        idx = self.service.next_event_index()
        self.assertEqual(idx, 1)


if __name__ == "__main__":
    unittest.main()
