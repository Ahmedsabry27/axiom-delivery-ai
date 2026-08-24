from asyncio import Queue


class RuntimeStream:
    def __init__(self):
        self.connections = {}

    def create(self, execution_id):

        self.connections[execution_id] = Queue()

        return execution_id

    async def publish(self, execution_id, event):

        queue = self.connections.get(execution_id)

        if queue:
            await queue.put(event)

    def subscribe(self, execution_id):

        return self.connections[execution_id]
