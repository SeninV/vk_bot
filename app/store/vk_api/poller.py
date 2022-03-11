import asyncio
from asyncio import Task
from typing import Optional

from app.store import Store


class Poller:
    def __init__(self, store: Store):
        self.store = store
        self.is_running = False
        self.poll_task: Optional[Task] = None

        self.queue = Optional[asyncio.Queue]
        self.tasks = []


    async def worker(self, queue):
        while True:
            update = await queue.get()
            await self.store.bots_manager.handle_updates(update[0])
            queue.task_done()


    async def start(self):
        self.is_running = True
        self.poll_task = asyncio.create_task(self.poll())

        self.queue = asyncio.Queue()
        for i in range(5):
            task = asyncio.create_task(self.worker(self.queue))
            self.tasks.append(task)

    async def stop(self):
        self.is_running = False
        await self.poll_task

        for task in self.tasks:
            task.cancel()

    async def poll(self):
        while self.is_running:
            updates = await self.store.vk_api.poll()
            if updates:
                self.queue.put_nowait(updates)
                # await self.store.bots_manager.handle_updates(updates)
