from app.base.base_accessor import BaseAccessor
from typing import List, Optional
from app.store.bot.models import UserModel, Game, GameModel, Score, ScoreModel



class BotAccessor(BaseAccessor):
    async def last_game(self, chat_id: int) -> Optional[Game]:
        last_game = (
            await GameModel.query.where(GameModel.chat_id == chat_id)
            .order_by(GameModel.id.desc())
            .gino.first()
        )
        if last_game:
            return last_game.to_dc()