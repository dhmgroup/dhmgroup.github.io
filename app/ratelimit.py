import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Sliding-window counter per key.

    ponytail: in-process memory, correct for a single uvicorn process only;
    move to Redis if the app ever runs more than one replica.
    """

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def _current(self, key: str) -> deque[float]:
        now = self.clock()
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        return hits

    def blocked(self, key: str) -> bool:
        """True when the key is at its limit; checking does not record a hit."""
        return len(self._current(key)) >= self.limit

    def hit(self, key: str) -> bool:
        if self.blocked(key):
            return False
        self._hits[key].append(self.clock())
        return True

    def clear(self) -> None:
        self._hits.clear()
