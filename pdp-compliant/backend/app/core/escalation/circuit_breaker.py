"""F5.4: circuit breaker for escalation provider failover."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_s: float = 60.0
    _state: BreakerState = field(default=BreakerState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _opened_at: float = field(default=0.0, init=False)

    @property
    def state(self) -> BreakerState:
        if self._state == BreakerState.OPEN and (time.monotonic() - self._opened_at) >= self.cooldown_s:
            self._state = BreakerState.HALF_OPEN
        return self._state

    def allow_request(self) -> bool:
        return self.state != BreakerState.OPEN

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = BreakerState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._state = BreakerState.OPEN
            self._opened_at = time.monotonic()
