import typing
from datetime import datetime
from logging import getLogger
import random
import time
from app.store.bot.models import ScoreModel, GameModel
from app.store.vk_api.dataclasses import Update, Message, KeyboardMessage

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
            await self.app.store.vk_api.send_message(
                Message(
                    text="\start - начало игры %0A \stat - статистика по игре  %0A \end - окончание по игры",
                    peer_id=update.object.peer_id,
                )
            )
