from datetime import datetime

from app.base.base_accessor import BaseAccessor
from typing import List, Optional

from app.quiz.schemes import ThemeListSchema
from app.store.bot.models import UserModel, Game, GameModel, Score, ScoreModel



class BotAccessor(BaseAccessor):
    async def connect(self, app: "Application"):
        await super().connect(app)
        themes = await self.app.store.quizzes.list_themes()
        data = ThemeListSchema().dump({"themes": themes})["themes"]
        self.themes = data


    def theme_response(self) -> str:
        text = ""
        themes = []
        for d in self.themes:
            themes.append(d["title"])
        for i, th in enumerate(themes):
                text += f"%0A ************ %0A {th}"
        return text



    async def create_game(
        self, chat_id: int) -> Game:
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