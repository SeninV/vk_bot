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
            a = 1
            if game:
                if update.object.body == "\start":

                    await self.app.store.bot_accessor.create_game(
                        chat_id=update.object.peer_id,
                    )
                    text_themes = self.app.store.bot_accessor.theme_response()
                    await self.app.store.vk_api.send_message(
                        Message(
                            text=f"Выберите тему: {text_themes}",
                            peer_id=update.object.peer_id,
                        )
                    )
                # else:
                    # for theme in themes:
                    #     if update.object.body == theme:
                    #         game_id = game.id
                    #         await self.start_game(update, theme, game_id)
                    #         # посылаем первую тему
                    #         await self.ask_question(update, theme, game_id)


            await self.app.store.vk_api.send_message(
                Message(
                    text="\start - начало игры %0A \stat - статистика по игре  %0A \end - окончание по игры",
                    peer_id=update.object.peer_id,
                )
            )
