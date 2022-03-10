import typing
import random
from logging import getLogger

from app.store.bot.models import GameModel
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

    async def start_game(self, update: Update):
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

    async def choose_theme(self, update: Update):
        themes = self.app.store.bot_accessor.themes
        for id in themes:
            if str(id["id"]) == update.object.body:
                unused_questions = []
                for question in await self.app.store.quizzes.list_questions(id["id"]):
                    unused_questions.append(question.id)

                await GameModel.update.where(
                    GameModel.chat_id == update.object.peer_id
                ).where(GameModel.status == "start").gino.first(
                    {
                        "theme_id": id["id"],
                        "status": "duration",
                        "unused_questions": unused_questions,
                    }
                )

                durations = self.app.store.bot_accessor.duration_response()
                await self.app.store.vk_api.send_message(
                    Message(
                        text=f"Выберите длительность раунда: {durations}",
                        peer_id=update.object.peer_id,
                    )
                )
                break

    async def choose_duration(
        self, update: Update, game_id: int, unused_questions: list[int]
    ):
        durations = self.app.store.bot_accessor.durations
        for duration in durations:
            if str(duration) == update.object.body:
                await GameModel.update.where(
                    GameModel.chat_id == update.object.peer_id
                ).where(GameModel.status == "duration").gino.first(
                    {"duration": duration, "status": "playing"}
                )

                existing_mambers = await self.app.store.bot_accessor.get_all_users_id()
                members = await self.app.store.vk_api.get_members(
                    chat_id=update.object.peer_id
                )

                for member in members:
                    if member["id"] not in existing_mambers:
                        await self.app.store.bot_accessor.create_user(
                            member["id"], member["first_name"], member["last_name"]
                        )

                    await self.app.store.bot_accessor.create_user_score(
                        game_id=game_id, user_id=member["id"], points=0, user_attempts=0
                    )

                question = await self.app.store.quizzes.get_question_by_id(
                    unused_questions[0]
                )
                keyboard_answer = self.app.store.bot_accessor.answer_response_keyboard(
                    question.answers
                )
                await self.app.store.vk_api.send_message(
                    Message(
                        text=f"Вопрос: {question.title} %0A" f"%0A {keyboard_answer}",
                        peer_id=update.object.peer_id,
                    )
                )
                break

    async def handle_updates(self, updates: list[Update]):
        for update in updates:
            game = await self.app.store.bot_accessor.last_game(update.object.peer_id)
            # Если раньше не было игр в беседе
            if not game:
                if update.object.body == "\start":
                    await self.start_game(update)
            else:
                # Если раньше были игры
                game_status = game.status
                if game_status == "end" and update.object.body == "\start":
                    await self.start_game(update)
                if game_status == "start":
                    await self.choose_theme(update)
                elif game_status == "duration":
                    await self.choose_duration(update, game.id, game.unused_questions)
                elif game_status == "playing":
                    pass

            await self.app.store.vk_api.send_message(
                Message(
                    text="\start - начало игры %0A \stat - статистика по игре  %0A \end - окончание по игры",
                    peer_id=update.object.peer_id,
                )
            )
