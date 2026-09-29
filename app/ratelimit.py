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

    def hit(self, key: str) -> bool:
        now = self.clock()
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def clear(self) -> None:
        self._hits.clear()
