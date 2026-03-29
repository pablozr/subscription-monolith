class AsyncContextManager:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeIncomingMessage:
    def __init__(self, body: bytes):
        self.body = body

    def process(self, requeue=True):
        return AsyncContextManager()
