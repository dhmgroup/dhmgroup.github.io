from app.ratelimit import RateLimiter


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(limit=3, window=60, clock=Clock())
    assert [limiter.hit("ip") for _ in range(4)] == [True, True, True, False]


def test_keys_are_independent():
    limiter = RateLimiter(limit=1, window=60, clock=Clock())
    assert limiter.hit("a") is True
    assert limiter.hit("b") is True
    assert limiter.hit("a") is False


def test_window_expires():
    clock = Clock()
    limiter = RateLimiter(limit=1, window=60, clock=clock)
    assert limiter.hit("ip") is True
    clock.now = 59.9
    assert limiter.hit("ip") is False
    clock.now = 60.1
    assert limiter.hit("ip") is True


def test_clear_resets_everything():
    limiter = RateLimiter(limit=1, window=60, clock=Clock())
    limiter.hit("ip")
    limiter.clear()
    assert limiter.hit("ip") is True


def test_blocked_checks_without_recording():
    limiter = RateLimiter(limit=2, window=60, clock=Clock())
    assert limiter.blocked("ip") is False
    assert limiter.blocked("ip") is False  # checking alone never uses up the allowance
    limiter.hit("ip")
    limiter.hit("ip")
    assert limiter.blocked("ip") is True
