"""Console status reporter for WHO step progress."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, TextIO

from deltawash_pi.interpreter.state_machine import InterpreterEvent, InterpreterEventType
from deltawash_pi.interpreter.types import StepID, StepState


def _default_now() -> float:
    return time.monotonic()


@dataclass
class _RowState:
    step_id: StepID
    state: StepState = StepState.NOT_STARTED
    accumulated_ms: int = 0


class ConsoleStatusReporter:
    """Renders the STEP | STATE | MS grid with 500 ms refresh cadence."""

    def __init__(
        self,
        steps: Sequence[StepID],
        *,
        refresh_interval: float = 0.5,
        output: Optional[TextIO] = None,
        now_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        if not steps:
            raise ValueError("ConsoleStatusReporter requires at least one step")
        self._steps = list(steps)
        self._rows: Dict[StepID, _RowState] = {step: _RowState(step) for step in self._steps}
        self._output = output or sys.stdout
        self._refresh_interval = max(0.1, float(refresh_interval))
        self._now = now_fn or _default_now
        self._session_id: Optional[str] = None
        self._active_step: Optional[StepID] = None
        self._last_render: float = 0.0
        self._dirty = False
        self._dirty_since: Optional[float] = None

    def start_session(self, session_id: str) -> None:
        """Initialize a new status grid for the given session."""

        self._session_id = session_id
        self._active_step = None
        for row in self._rows.values():
            row.state = StepState.NOT_STARTED
            row.accumulated_ms = 0
        self._mark_dirty()
        self._last_render = 0.0
        self._render(force=True)

    def end_session(self) -> None:
        """Render the final grid and clear active markers."""

        if self._session_id is None:
            return
        self._active_step = None
        self._render(force=True)
        self._session_id = None
        self._dirty = False
        self._dirty_since = None

    def handle_event(self, event: InterpreterEvent) -> None:
        """Consume interpreter events to update the grid."""

        if self._session_id is None or event.session_id != self._session_id:
            return
        if event.event_type is InterpreterEventType.STEP_STATE and event.step_id is not None:
            row = self._rows.get(event.step_id)
            if row is None:
                return
            if event.state is not None:
                row.state = event.state
            accumulated = event.details.get("accumulated_ms")
            if isinstance(accumulated, (int, float)):
                row.accumulated_ms = max(0, int(round(accumulated)))
            self._mark_dirty()
        elif event.event_type is InterpreterEventType.ACTIVE_STEP:
            active = event.details.get("active_step")
            if isinstance(active, str) and active:
                try:
                    self._active_step = StepID(active)
                except ValueError:
                    self._active_step = None
            else:
                self._active_step = None
            self._mark_dirty()
        self._render()

    def force_render(self) -> None:
        """Render immediately regardless of throttling."""

        self._render(force=True)

    def _render(self, *, force: bool = False) -> None:
        if not self._dirty and not force:
            return
        now = self._now()
        if not force and now - self._last_render < self._refresh_interval:
            return
        lines = self._build_lines()
        self._output.write("\n".join(lines) + "\n")
        self._output.flush()
        if self._dirty_since is not None:
            latency = max(0.0, now - self._dirty_since)
            self._record_latency(latency)
        self._dirty = False
        self._dirty_since = None
        self._last_render = now

    def _build_lines(self) -> List[str]:
        lines = ["STEP | STATE        | MS", "------------------------"]
        for row in self._ordered_rows():
            marker = self._marker_for_row(row)
            label = row.step_id.value.replace("STEP_", "")
            prefix = f"{marker}{label}".ljust(4)
            state_str = row.state.value
            ms_value = min(row.accumulated_ms, 99999)
            lines.append(f"{prefix} | {state_str:<12} | {ms_value:05d}")
        return lines

    def _ordered_rows(self) -> List[_RowState]:
        return [self._rows[step] for step in self._steps]

    def _marker_for_row(self, row: _RowState) -> str:
        if row.state is StepState.COMPLETED:
            return "*"
        if self._active_step is row.step_id:
            return ">"
        return " "

    def _mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            if self._dirty_since is None:
                self._dirty_since = self._now()

    def _record_latency(self, latency: float) -> None:
        del latency


__all__ = ["ConsoleStatusReporter"]
