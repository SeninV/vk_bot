import typing
import random
from logging import getLogger

from app.store.bot.models import GameModel, GameStatus
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

    async def start_game(self, update: Update):
        await self.app.store.bot_accessor.create_game(
            chat_id=update.object.peer_id,
        )
        themes = await self.app.store.quizzes.list_themes()
        text_themes = self.app.store.bot_accessor.theme_response(themes)
        await self.app.store.vk_api.send_message(
            Message(
                text=f"Выберите номер темы: {text_themes}",
                peer_id=update.object.peer_id,
            )
        )

    async def choose_theme(self, update: Update):
        theme = await self.app.store.quizzes.get_theme_by_id(int(update.object.body))
        if theme:
            questions = await self.app.store.quizzes.list_questions(theme_id=theme.id)
            unused_questions = [question.id for question in questions]

            await self.app.store.bot_accessor.update_game_theme(
                chat_id=update.object.peer_id,
                status="duration",
                theme_id=theme.id,
                unused_questions=unused_questions,
            )
            return True

    async def send_durations(self, update: Update):
        durations = self.app.store.bot_accessor.duration_response()
        await self.app.store.vk_api.send_message(
            Message(
                text=f"Выберите длительность раунда: {durations}",
                peer_id=update.object.peer_id,
            )
        )

    async def choose_duration(self, update: Update, game_id: int):
        durations = self.app.store.bot_accessor.durations
        if int(update.object.body) in durations:
            await self.app.store.bot_accessor.update_game_duration(
                chat_id=update.object.peer_id,
                status="playing",
                duration=int(update.object.body),
            )

            users = await self.app.store.bot_accessor.get_all_users()
            existing_members = [user.user_id for user in users]

            members = await self.app.store.vk_api.get_members(
                chat_id=update.object.peer_id
            )

            for member in members:
                if member["id"] not in existing_members:
                    await self.app.store.bot_accessor.create_user(
                        member["id"], member["first_name"], member["last_name"]
                    )

                await self.app.store.bot_accessor.create_user_score(
                    game_id=game_id, user_id=member["id"], points=0, user_attempts=0
                )
            return True

    async def ask_question(self, update: Update, unused_questions: list[int]):
        question = await self.app.store.quizzes.get_question_by_id(unused_questions[0])
        keyboard_answer = self.app.store.bot_accessor.answer_response_keyboard(
            question.answers
        )
        await self.app.store.vk_api.send_keyboard(
            KeyboardMessage(
                text=f"Вопрос: {question.title} %0A",
                peer_id=update.object.peer_id,
                keyboard_text=keyboard_answer,
            )
        )

    async def game_over(self, update: Update, game_id: int):
        await self.app.store.bot_accessor.update_game_over(
            chat_id=update.object.peer_id
        )
        participants = await self.app.store.bot_accessor.stat_game_response(
            game_id=game_id
        )
        await self.app.store.vk_api.delet_keyboard(
            Message(
                text=f"Конец игры! %0A Итоговый счет: {participants}",
                peer_id=update.object.peer_id,
            )
        )

    async def checking_next_question(
        self, update: Update, game_id: int, unused_questions: list[int]
    ):
        if unused_questions[1:]:
            await self.app.store.bot_accessor.update_game_unused_questions(
                chat_id=update.object.peer_id, unused_questions=unused_questions[1:]
            )
            await self.app.store.bot_accessor.reset_to_zero_attempts(game_id=game_id)
            await self.ask_question(update, unused_questions=unused_questions[1:])
        else:
            await self.game_over(update, game_id=game_id)

    async def response_processing(
        self, update: Update, game_id: int, unused_questions: list[int]
    ):
        users_with_attempts_list = (
            await self.app.store.bot_accessor.get_users_with_attempts(game_id=game_id)
        )
        # проверка кол-ва попыток у пользователя
        if update.object.user_id in users_with_attempts_list:
            question = await self.app.store.quizzes.get_question_by_id(
                unused_questions[0]
            )
            right_answer = self.app.store.bot_accessor.get_answer(question.answers)
            if (
                update.object.body == right_answer
                or update.object.body
                == f"[club206933962|@club206933962] {right_answer}"
            ):
                await self.app.store.bot_accessor.update_user_score(
                    game_id=game_id, user_id=update.object.user_id
                )
                await self.app.store.vk_api.send_message(
                    Message(
                        text=f"Правильный ответ дал пользователь @id{update.object.user_id}",
                        peer_id=update.object.peer_id,
                    )
                )
                # Если остались еще вопросы
                await self.checking_next_question(
                    update=update, game_id=game_id, unused_questions=unused_questions
                )

            else:
                await self.app.store.bot_accessor.increase_user_attempts(
                    game_id=game_id, user_id=update.object.user_id
                )
                # Если больше не осталось пользователей с попытками
                if not users_with_attempts_list[1:]:
                    await self.checking_next_question(
                        update=update,
                        game_id=game_id,
                        unused_questions=unused_questions,
                    )

    async def handle_updates(self, update: Update):
        game = await self.app.store.bot_accessor.last_game(update.object.peer_id)
        # Если раньше не было игр в беседе
        if not game:
            if update.object.body == "\start":
                await self.start_game(update)
        else:
            # Если раньше были игры
            game_status = game.status
            if game_status == GameStatus.FINISH and update.object.body == "\start":
                await self.start_game(update)
            if game_status == GameStatus.START and update.object.body.isdigit():
                if await self.choose_theme(update):
                    await self.send_durations(update)
            elif game_status == GameStatus.DURATION and update.object.body.isdigit():
                if await self.choose_duration(update, game_id=game.id):
                    await self.ask_question(
                        update, unused_questions=game.unused_questions
                    )
            elif game_status == GameStatus.PLAYING:
                await self.response_processing(
                    update, game_id=game.id, unused_questions=game.unused_questions
                )

        await self.app.store.vk_api.send_message(
            Message(
                text="\start - начало игры %0A \stat - статистика по игре  %0A \end - окончание по игры",
                peer_id=update.object.peer_id,
            )
        )
