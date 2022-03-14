import asyncio
import typing
import random
from asyncio import Task
from datetime import datetime
from logging import getLogger

from app.store.bot.models import GameModel, GameStatus, TimeoutTask, Game
from app.store.vk_api.dataclasses import Update, Message, KeyboardMessage

if typing.TYPE_CHECKING:
    from app.web.app import Application


class BotManager:
    def __init__(self, app: "Application"):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")
        self.game_timeout_tasks: list[TimeoutTask] = []
        self.question_timeout_tasks: list[TimeoutTask] = []

    def create_game_timeout_callback(self, task: Task):
        async def check_game(task: Task):
            game_id = task.result()["game_id"]
            update = task.result()["update"]
            await self.app.store.vk_api.send_message(
                Message(
                    text=f"Время игры истекло",
                    peer_id=update.object.peer_id,
                )
            )
            await self.game_over(update, game_id=game_id)

        asyncio.create_task(coro=check_game(task=task))

    def create_question_timeout_callback(self, task: Task):
        async def check_question(task: Task):
            game_id = task.result()["game_id"]
            update = task.result()["update"]
            unused_questions = task.result()["unused_questions"]
            time_to_sleep = task.result()["time_to_sleep"]

            question = await self.app.store.quizzes.get_question_by_id(
                unused_questions[0]
            )
            right_answer = self.app.store.bot_accessor.get_answer(question.answers)

            await self.app.store.vk_api.send_message(
                Message(
                    text=f"Время на вопрос истекло %0A Правильный ответ: {right_answer}",
                    peer_id=update.object.peer_id,
                )
            )
            await self.checking_last_question(
                update=update,
                game_id=game_id,
                unused_questions=unused_questions[1:],
                time_to_sleep=time_to_sleep,
            )

        asyncio.create_task(coro=check_question(task=task))

    async def timeout_task_game(self, update: Update, game_id: int, sleep: int):
        return await asyncio.sleep(
            delay=sleep,
            result={
                "update": update,
                "game_id": game_id,
            },
        )

    async def timeout_task_question(
        self, update: Update, game_id: int, sleep: int, unused_questions: list[int]
    ):
        return await asyncio.sleep(
            delay=sleep,
            result={
                "update": update,
                "game_id": game_id,
                "unused_questions": unused_questions,
                "time_to_sleep": sleep,
            },
        )

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

    async def choose_theme(self, update: Update) -> bool:
        theme = await self.app.store.quizzes.get_theme_by_id(int(update.object.body))
        if not theme:
            return False
        else:
            questions = await self.app.store.quizzes.list_questions(theme_id=theme.id)
            unused_questions = [question.id for question in questions]

            await self.app.store.bot_accessor.update_game_theme(
                chat_id=update.object.peer_id,
                status="duration",
                theme_id=theme.id,
                unused_questions=unused_questions,
            )
            return True

    async def send_game_durations(self, update: Update):
        durations = self.app.store.bot_accessor.game_duration_response()
        await self.app.store.vk_api.send_message(
            Message(
                text=f"Выберите длительность раунда: {durations}",
                peer_id=update.object.peer_id,
            )
        )

    async def choose_game_duration(self, update: Update, game_id: int) -> bool:
        durations = self.app.store.bot_accessor.game_durations
        if not int(update.object.body) in durations:
            return False
        else:
            await self.app.store.bot_accessor.update_game_duration(
                chat_id=update.object.peer_id,
                status="duration_question",
                duration=int(update.object.body) * 60,
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

    async def send_question_durations(self, update: Update):
        durations = self.app.store.bot_accessor.question_duration_response()
        await self.app.store.vk_api.send_message(
            Message(
                text=f"Выберите длительность каждого вопроса: {durations}",
                peer_id=update.object.peer_id,
            )
        )

    async def choose_question_duration(
        self,
        update: Update,
        game_id: int,
        game_duration: int,
        unused_questions: list[int],
    ) -> bool:
        durations = self.app.store.bot_accessor.question_durations
        if not int(update.object.body) in durations:
            return False
        else:

            await self.app.store.bot_accessor.update_question_duration(
                chat_id=update.object.peer_id,
                status="playing",
                duration=int(update.object.body),
            )

            game_task = asyncio.create_task(
                self.timeout_task_game(
                    update=update, game_id=game_id, sleep=game_duration
                )
            )
            game_task.add_done_callback(self.create_game_timeout_callback)

            self.game_timeout_tasks.append(
                TimeoutTask(
                    game_id=game_id,
                    chat_id=update.object.peer_id,
                    task=game_task,
                )
            )

            question_task = asyncio.create_task(
                self.timeout_task_question(
                    update=update,
                    game_id=game_id,
                    sleep=int(update.object.body),
                    unused_questions=unused_questions,
                )
            )
            question_task.add_done_callback(self.create_question_timeout_callback)

            self.question_timeout_tasks.append(
                TimeoutTask(
                    game_id=game_id,
                    chat_id=update.object.peer_id,
                    task=question_task,
                )
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

        winner = await self.app.store.bot_accessor.get_winner(game_id=game_id)

        await self.app.store.bot_accessor.update_game_over(
            chat_id=update.object.peer_id, winner=winner
        )
        participants = await self.app.store.bot_accessor.stat_game_response(
            game_id=game_id
        )
        for timeout_task in self.game_timeout_tasks:
            if timeout_task.game_id == game_id:
                timeout_task.task.remove_done_callback(
                    self.create_game_timeout_callback
                )
                timeout_task.task.cancel()
                self.game_timeout_tasks.remove(timeout_task)
                break

        for timeout_task in self.question_timeout_tasks:
            if timeout_task.game_id == game_id:
                timeout_task.task.remove_done_callback(
                    self.create_question_timeout_callback
                )
                timeout_task.task.cancel()
                self.question_timeout_tasks.remove(timeout_task)
                break

        await self.app.store.bot_accessor.update_win_count(
            game_id=game_id, winner=winner
        )

        await self.app.store.vk_api.delete_keyboard(
            Message(
                text=f"Конец игры! %0A Итоговый счет: {participants}",
                peer_id=update.object.peer_id,
            )
        )

    async def checking_last_question(
        self,
        update: Update,
        game_id: int,
        unused_questions: list[int],
        time_to_sleep: int,
    ):
        if not unused_questions:
            await self.game_over(update, game_id=game_id)
        else:
            await self.app.store.bot_accessor.update_game_unused_questions(
                chat_id=update.object.peer_id, unused_questions=unused_questions
            )
            await self.app.store.bot_accessor.reset_to_zero_attempts(game_id=game_id)
            await self.ask_question(update, unused_questions=unused_questions)

            for timeout_task in self.question_timeout_tasks:
                if timeout_task.game_id == game_id:
                    timeout_task.task.remove_done_callback(
                        self.create_question_timeout_callback
                    )
                    timeout_task.task.cancel()
                    self.question_timeout_tasks.remove(timeout_task)
                    break

            question_task = asyncio.create_task(
                self.timeout_task_question(
                    update=update,
                    game_id=game_id,
                    sleep=time_to_sleep,
                    unused_questions=unused_questions,
                )
            )
            question_task.add_done_callback(self.create_question_timeout_callback)

            self.question_timeout_tasks.append(
                TimeoutTask(
                    game_id=game_id,
                    chat_id=update.object.peer_id,
                    task=question_task,
                )
            )

    async def response_processing(
        self,
        update: Update,
        game_id: int,
        unused_questions: list[int],
        time_to_sleep: int,
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
                await self.checking_last_question(
                    update=update,
                    game_id=game_id,
                    unused_questions=unused_questions[1:],
                    time_to_sleep=time_to_sleep,
                )

            else:
                await self.app.store.bot_accessor.increase_user_attempts(
                    game_id=game_id, user_id=update.object.user_id
                )
                # Если больше не осталось пользователей с попытками
                if not users_with_attempts_list[1:]:

                    await self.app.store.vk_api.send_message(
                        Message(
                            text=f"Никто не ответил правильно( %0A Правильный ответ: {right_answer}",
                            peer_id=update.object.peer_id,
                        )
                    )
                    await self.checking_last_question(
                        update=update,
                        game_id=game_id,
                        unused_questions=unused_questions[1:],
                        time_to_sleep=time_to_sleep,
                    )

    async def game_stats(
        self, update: Update, game_id: int, duration: int, time: datetime, status: str
    ):
        if status == GameStatus.PLAYING:
            time_to_end = round(
                duration + time.timestamp() - datetime.now().timestamp()
            )
            participants = await self.app.store.bot_accessor.stat_game_response(
                game_id=game_id
            )
            await self.app.store.vk_api.send_message(
                Message(
                    text=f"Cчет игры: {participants}"
                    f"%0A Время до конца игры: {time_to_end} сек",
                    peer_id=update.object.peer_id,
                )
            )
        elif status == GameStatus.FINISH:
            participants = await self.app.store.bot_accessor.stat_game_response(
                game_id=game_id
            )
            await self.app.store.vk_api.send_message(
                Message(
                    text=f"Cчет игры: {participants}",
                    peer_id=update.object.peer_id,
                )
            )

    async def game_pause(self, update: Update, game: Game):
        time_left = round(
            game.duration_game + game.start.timestamp() - datetime.now().timestamp()
        )
        a = 1
        #     Останавливаем таски
        for timeout_task in self.game_timeout_tasks:
            if timeout_task.game_id == game.id:
                timeout_task.task.remove_done_callback(
                    self.create_game_timeout_callback
                )
                timeout_task.task.cancel()
                self.game_timeout_tasks.remove(timeout_task)
                break

        for timeout_task in self.question_timeout_tasks:
            if timeout_task.game_id == game.id:
                timeout_task.task.remove_done_callback(
                    self.create_question_timeout_callback
                )
                timeout_task.task.cancel()
                self.question_timeout_tasks.remove(timeout_task)
                break

        await self.app.store.bot_accessor.update_game_pause(
            chat_id=update.object.peer_id,
            status="pause",
            duration=time_left,
        )

        participants = await self.app.store.bot_accessor.stat_game_response(
            game_id=game.id
        )
        await self.app.store.vk_api.delete_keyboard(
            Message(
                text=f"Игра на паузе %0A Текущий счет: {participants}",
                peer_id=update.object.peer_id,
            )
        )

    async def game_continue(self, update: Update, game: Game):

        await self.app.store.bot_accessor.update_game_continue(
            chat_id=update.object.peer_id,
            status="playing",
        )
        # Возобновляем таски
        game_task = asyncio.create_task(
            self.timeout_task_game(
                update=update, game_id=game.id, sleep=game.duration_game
            )
        )
        game_task.add_done_callback(self.create_game_timeout_callback)

        self.game_timeout_tasks.append(
            TimeoutTask(
                game_id=game.id,
                chat_id=update.object.peer_id,
                task=game_task,
            )
        )

        question_task = asyncio.create_task(
            self.timeout_task_question(
                update=update,
                game_id=game.id,
                sleep=game.duration_question,
                unused_questions=game.unused_questions,
            )
        )
        question_task.add_done_callback(self.create_question_timeout_callback)

        self.question_timeout_tasks.append(
            TimeoutTask(
                game_id=game.id,
                chat_id=update.object.peer_id,
                task=question_task,
            )
        )

        await self.ask_question(update, unused_questions=game.unused_questions)

    async def handle_updates(self, update: Update):
        game = await self.app.store.bot_accessor.last_game(update.object.peer_id)
        # Если раньше не было игр в беседе
        if not game:
            if update.object.body == "\start":
                await self.start_game(update)
            else:
                await self.app.store.vk_api.send_message(
                    Message(
                        text="\start - начало игры",
                        peer_id=update.object.peer_id,
                    )
                )
        else:
            # Если раньше были игры
            game_status = game.status
            if update.object.body == "\stat":
                await self.game_stats(
                    update,
                    game_id=game.id,
                    duration=game.duration_game,
                    time=game.start,
                    status=game_status,
                )
            elif game_status == GameStatus.FINISH and update.object.body == "\start":
                await self.start_game(update=update)
            elif game_status == GameStatus.START and update.object.body.isdigit():
                if await self.choose_theme(update=update):
                    await self.send_game_durations(update=update)
            elif game_status == GameStatus.DURATION and update.object.body.isdigit():
                if await self.choose_game_duration(update=update, game_id=game.id):
                    await self.send_question_durations(update=update)

            elif (
                game_status == GameStatus.DURATION_QUESTION
                and update.object.body.isdigit()
            ):
                if await self.choose_question_duration(
                    update=update,
                    game_id=game.id,
                    game_duration=game.duration_game,
                    unused_questions=game.unused_questions,
                ):
                    await self.ask_question(
                        update, unused_questions=game.unused_questions
                    )

            elif game_status == GameStatus.PLAYING:
                if update.object.body == "\pause":
                    await self.game_pause(update=update, game=game)
                else:
                    await self.response_processing(
                        update,
                        game_id=game.id,
                        unused_questions=game.unused_questions,
                        time_to_sleep=game.duration_question,
                    )
            elif game_status == GameStatus.PAUSE:
                if update.object.body == "\continue":
                    await self.game_continue(update=update, game=game)

            else:
                await self.app.store.vk_api.send_message(
                    Message(
                        text="\start - начало игры %0A \stat - статистика по игре  %0A \pause - пауза в игре %0A \continue - продолжение игры",
                        peer_id=update.object.peer_id,
                    )
                )
