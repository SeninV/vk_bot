import typing
from logging import getLogger
from app.store.vk_api.dataclasses import Update, Message

if typing.TYPE_CHECKING:
    from app.web.app import Application


class BotManager:
    def __init__(self, app: "Application"):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")
        self.start = {}
        self.time = {}

    async def handle_updates(self, updates: list[Update]):
        for update in updates:
            game = await self.app.store.bot_accessor.last_game(update.object.peer_id)
            await self.app.store.vk_api.send_message(
                Message(
                    text="\start - начало игры %0A \stat - статистика по игре  %0A \end - окончание по игры",
                    peer_id=update.object.peer_id,
                )
            )