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
        themes = await self.app.store.quizzes.list_themes()
        data = ThemeListSchema().dump({"themes": themes})["themes"]
        # Список возможных тем
        self.themes = data
        # Возможное время игры в минутах
        games_duration = [3, 4, 5]
        self.durations = games_duration

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

    async def get_all_users_id(self) -> Optional[list]:
        user_list = await self.get_all_users()
        if not user_list:
            return user_list
        user_list = UserListSchema().dump({"users": user_list})["users"]
        user_id_list = []
        for user in user_list:
            user_id_list.append(user["user_id"])
        return user_id_list

    def theme_response(self) -> str:
        text = ""
        themes = []
        for d in self.themes:
            themes.append(d["title"])
        for i, th in enumerate(themes):
            text += f"%0A ************ %0A {i+1} - {th}"
        return text

    def duration_response(self) -> str:
        text = ""
        for duration in self.durations:
            text += f" %0A {duration} мин"
        return text

    async def create_game(self, chat_id: int) -> Game:
        game = await GameModel.create(
            chat_id=chat_id,
            status="start",
            duration=0,
            theme_id=1,
            unused_questions="",
        )
        return game.to_dc()

    async def last_game(self, chat_id: int) -> Optional[Game]:
        last_game = (
            await GameModel.query.where(GameModel.chat_id == chat_id)
            .order_by(GameModel.id.desc())
            .gino.first()
        )
        if not last_game:
            return None
        return last_game.to_dc()

    def answer_response_keyboard(self, answer: List[Answer]) -> List[str]:
        text = []
        for ans in answer:
            text += [ans.title]
        return text
