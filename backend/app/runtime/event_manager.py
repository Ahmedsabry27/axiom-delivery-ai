from collections import defaultdict
from queue import Queue


class RuntimeEventManager:
    def __init__(self):

        self.listeners = defaultdict(list)

    def publish(self, execution_id, event):

        for queue in self.listeners[execution_id]:
            queue.put(event)

    def subscribe(self, execution_id):

        queue = Queue()

        self.listeners[execution_id].append(queue)

        return queue


runtime_events = RuntimeEventManager()
