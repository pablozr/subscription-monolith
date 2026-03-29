class AsyncContextManager:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeIncomingMessage:
    def __init__(self, body: bytes, headers: dict | None = None):
        self.body = body
        self.headers = headers or {}
        self.acked = False
        self.nacked = False
        self.requeued = None

    def process(self, requeue=True):
        return AsyncContextManager()

    async def ack(self):
        self.acked = True

    async def nack(self, requeue=True):
        self.nacked = True
        self.requeued = requeue
