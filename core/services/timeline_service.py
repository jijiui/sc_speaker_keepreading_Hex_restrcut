from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Sequence

from core.domain import TimelineEvent

AnnouncementKind = Literal["on_time", "early"]


@dataclass(frozen=True)
class AnnouncementDecision:
    """Result returned when一条事件需要播报."""

    event: TimelineEvent
    kind: AnnouncementKind
    trigger_ms: int


class TimelineService:
    """Pure-Python service that manages flows and announcement logic."""

    def __init__(self, *, global_lead_ms: int = 2000) -> None:
        self.global_lead_ms = max(0, int(global_lead_ms))
        self.on_time_enabled = True
        self.early_enabled = False

        self._flows: Dict[str, List[TimelineEvent]] = {}
        self._current_flow: Optional[str] = None

        self._elapsed_ms = 0
        self._prev_ms = 0
        self._running = False

    # ------------------------------------------------------------------
    # Flows / state
    # ------------------------------------------------------------------

    @property
    def elapsed_ms(self) -> int:
        return self._elapsed_ms

    @property
    def prev_ms(self) -> int:
        return self._prev_ms

    @property
    def running(self) -> bool:
        return self._running

    @property
    def current_flow_name(self) -> Optional[str]:
        return self._current_flow

    def set_flows(self, flows: Dict[str, Sequence[TimelineEvent]]) -> None:
        """Replace all flows with sorted copies."""
        normalized: Dict[str, List[TimelineEvent]] = {}
        for name, events in flows.items():
            normalized[name] = sorted(list(events), key=lambda ev: ev.time_ms)
        self._flows = normalized
        if self._current_flow not in self._flows:
            self._current_flow = None
        self.reset()

    def flow_names(self) -> List[str]:
        return list(self._flows.keys())

    def get_events(self, name: Optional[str] = None) -> List[TimelineEvent]:
        flow = name if name is not None else self._current_flow
        if flow is None:
            return []
        return list(self._flows.get(flow, []))

    def set_current_flow(self, name: str) -> List[TimelineEvent]:
        if name not in self._flows:
            raise KeyError(f"未知流程：{name}")
        self._current_flow = name
        self.reset()
        return self.get_events()

    # ------------------------------------------------------------------
    # Runtime control
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._current_flow is None:
            raise RuntimeError("尚未选择流程，无法开始计时")
        self._running = True
        self._prev_ms = self._elapsed_ms

    def pause(self) -> None:
        self._running = False
        self._prev_ms = self._elapsed_ms

    def reset(self) -> None:
        self._running = False
        self._elapsed_ms = 0
        self._prev_ms = 0

    def set_global_lead(self, ms: int) -> None:
        self.global_lead_ms = max(0, int(ms))

    # ------------------------------------------------------------------
    # Time progression
    # ------------------------------------------------------------------

    def advance(self, delta_ms: int) -> Optional[AnnouncementDecision]:
        """Advance elapsed time by delta, returning announcement decision."""
        if not self._running or delta_ms <= 0:
            return None
        prev = self._elapsed_ms
        self._elapsed_ms += delta_ms
        decision = self._check_announcements(prev, self._elapsed_ms)
        self._prev_ms = self._elapsed_ms
        return decision

    def sync_elapsed(self, target_ms: int) -> Optional[AnnouncementDecision]:
        """Force elapsed time to the specified value (e.g., OCR correction)."""
        prev = self._elapsed_ms
        self._elapsed_ms = max(0, int(target_ms))
        decision = self._check_announcements(prev, self._elapsed_ms)
        self._prev_ms = self._elapsed_ms
        return decision

    def prime_elapsed(self, target_ms: int) -> None:
        """Align elapsed/prev without触发播报（第一次锁定 OCR 时使用）。"""
        self._elapsed_ms = max(0, int(target_ms))
        self._prev_ms = self._elapsed_ms

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def next_event_index(self, *, ref_ms: Optional[int] = None) -> Optional[int]:
        events = self.get_events()
        if not events:
            return None
        target = self._elapsed_ms if ref_ms is None else ref_ms
        for idx, ev in enumerate(events):
            if ev.time_ms >= target:
                return idx
        return len(events) - 1

    def _check_announcements(
        self,
        prev_ms: int,
        curr_ms: int,
    ) -> Optional[AnnouncementDecision]:
        events = self.get_events()
        if not events or curr_ms < prev_ms:
            return None
        advance_ms = self.global_lead_ms if self.early_enabled else 0
        for ev in events:
            if self.on_time_enabled and (prev_ms < ev.time_ms <= curr_ms):
                return AnnouncementDecision(ev, "on_time", curr_ms)
            if advance_ms > 0:
                early_start = max(0, ev.time_ms - advance_ms)
                if (prev_ms < early_start <= curr_ms) and (curr_ms < ev.time_ms):
                    return AnnouncementDecision(ev, "early", curr_ms)
        return None
