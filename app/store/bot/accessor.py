from datetime import datetime

from app.admin.schemes import UserListSchema
from app.base.base_accessor import BaseAccessor
from typing import List, Optional

from app.quiz.models import Answer
from app.quiz.schemes import ThemeListSchema
from app.store.bot.models import UserModel, Game, GameModel, Score, ScoreModel


class BotAccessor(BaseAccessor):
    async def connect(self, app: "Application"):
        await super().connect(app)
        # Возможное время игры в минутах
        self.game_durations = [1, 2, 3, 4, 5]
        self.question_durations = [10, 20, 30]

    async def create_user(self, user_id: int, first_name: str, last_name: str):
        await UserModel.create(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            win_count=0,
        )

    async def create_user_score(
        self, game_id: int, user_id: int, points: int, user_attempts: int
    ) -> Score:
        score = await ScoreModel.create(
            game_id=game_id, user_id=user_id, points=points, user_attempts=user_attempts
        )
        return score.to_dc()

    async def get_all_users(self) -> Optional[list]:
        user_list = await UserModel.query.gino.all()
        return [o.to_dc() for o in user_list]

    async def get_users_with_attempts(self, game_id: int) -> Optional[list]:
        score_list = (
            await ScoreModel.query.where(ScoreModel.game_id == game_id)
            .where(ScoreModel.user_attempts == 0)
            .gino.all()
        )
        return [o.to_dc().user_id for o in score_list]

    async def update_user_score(self, game_id: int, user_id: int):
        await ScoreModel.update.values(points=1 + ScoreModel.points).where(
            ScoreModel.game_id == game_id
        ).where(ScoreModel.user_id == user_id).gino.all()

    async def increase_user_attempts(self, game_id: int, user_id: int):
        await ScoreModel.update.values(user_attempts=1).where(
            ScoreModel.game_id == game_id
        ).where(ScoreModel.user_id == user_id).gino.all()

    async def reset_to_zero_attempts(self, game_id: int):
        await ScoreModel.update.values(user_attempts=0).where(
            ScoreModel.game_id == game_id
        ).gino.all()

    def theme_response(self, themes_all) -> str:
        text = ""
        themes = []
        for d in themes_all:
            themes.append(d.title)
        for i, th in enumerate(themes):
            text += f"%0A ************ %0A {i+1} - {th}"
        return text

    def game_duration_response(self) -> str:
        text = ""
        for duration in self.game_durations:
            text += f" %0A {duration} мин"
        return text

    def question_duration_response(self) -> str:
        text = ""
        for duration in self.question_durations:
            text += f" %0A {duration} сек"
        return text

    def answer_response_keyboard(self, answer: List[Answer]) -> List[str]:
        text = []
        for ans in answer:
            text += [ans.title]
        return text

    def get_answer(self, answer: List[Answer]) -> str:
        for ans in answer:
            if ans.is_correct:
                return ans.title

    async def create_game(self, chat_id: int) -> Game:
        game = await GameModel.create(
            chat_id=chat_id,
            status="start",
            duration_game=0,
            duration_question=0,
            theme_id=1,
            unused_questions="",
        )
        return game.to_dc()

    async def update_game_theme(
        self, chat_id: int, status: str, theme_id: int, unused_questions: list[int]
    ):
        await GameModel.update.where(GameModel.chat_id == chat_id).where(
            GameModel.status == "start"
        ).gino.first(
            {
                "status": status,
                "theme_id": theme_id,
                "unused_questions": unused_questions,
            }
        )

    async def update_game_duration(self, chat_id: int, status: str, duration: int):
        await GameModel.update.where(GameModel.chat_id == chat_id).where(
            GameModel.status == "duration"
        ).gino.first(
            {
                "status": status,
                "duration_game": duration,
            }
        )

    async def update_question_duration(self, chat_id: int, status: str, duration: int):
        await GameModel.update.where(GameModel.chat_id == chat_id).where(
            GameModel.status == "duration_question"
        ).gino.first(
            {
                "status": status,
                "start": datetime.now(),
                "duration_question": duration,
            }
        )

    async def update_game_unused_questions(
        self, chat_id: int, unused_questions: list[int]
    ):
        await GameModel.update.where(GameModel.chat_id == chat_id).where(
            GameModel.status == "playing"
        ).gino.first(
            {
                "unused_questions": unused_questions,
            }
        )

    async def update_game_pause(self, chat_id: int, status: str, duration: int):
        await GameModel.update.where(GameModel.chat_id == chat_id).where(
            GameModel.status == "playing"
        ).gino.first(
            {
                "status": status,
                "duration_game": duration,
            }
        )

    async def update_game_continue(self, chat_id: int, status: str):
        await GameModel.update.where(GameModel.chat_id == chat_id).where(
            GameModel.status == "pause"
        ).gino.first(
            {
                "status": status,
                "start": datetime.now(),
            }
        )

    async def update_game_over(self, chat_id: int):
        await GameModel.update.where(GameModel.chat_id == chat_id).where(
            GameModel.status == "playing"
        ).gino.first(
            {
                "status": "finish",
                "end": datetime.now(),
                "unused_questions": {},
            }
        )

    async def last_game(self, chat_id: int) -> Optional[Game]:
        last_game = (
            await GameModel.query.where(GameModel.chat_id == chat_id)
            .order_by(GameModel.id.desc())
            .gino.first()
        )
        if not last_game:
            return None
        return last_game.to_dc()

    async def played_game_status(self, game_id: int) -> Optional[Game]:
        played_game = await GameModel.query.where(GameModel.id == game_id).gino.first()
        return played_game.to_dc().status

    async def played_game_questions(self, game_id: int) -> Optional[Game]:
        played_game = await GameModel.query.where(GameModel.id == game_id).gino.first()
        return played_game.to_dc().unused_questions

    async def stat_game_response(self, game_id: int) -> str:
        participants = (
            await ScoreModel.query.where(ScoreModel.game_id == game_id)
            .order_by(ScoreModel.points.desc())
            .gino.all()
        )
        text = ""
        for i, par in enumerate(participants, 1):
            text += f"%0A {i}) @id{par.user_id} - {par.points}"
        return text
