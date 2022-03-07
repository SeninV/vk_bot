from dataclasses import dataclass
from datetime import datetime
from typing import List
from sqlalchemy.sql import func

from app.store.database.gino import db


@dataclass
class Game:
    id: int
    chat_id: int
    status: str
    start: datetime
    end: datetime
    duration: int
    theme_id: int
    unused_questions: List[str]


class GameModel(db.Model):
    __tablename__ = "games"

    id = db.Column(db.Integer(), primary_key=True)
    chat_id = db.Column(db.Integer(), nullable=False)
    status = db.Column(db.String(), nullable=False)
    start = db.Column(db.DateTime(), server_default=func.now())
    end = db.Column(db.DateTime(), nullable=False)
    duration = db.Column(db.Integer(), nullable=False)
    theme_id = db.Column(db.Integer(), db.ForeignKey("themes.id", ondelete="CASCADE"))
    unused_questions = db.Column(db.ARRAY(db.String()))

    def to_dc(self):
        return Game(**self.svalue)


@dataclass
class User:
    id: int
    user_id: int
    first_name: str
    last_name: str
    win_count: int


class UserModel(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), nullable=False, unique=True)
    first_name = db.Column(db.String(), nullable=False)
    last_name = db.Column(db.String(), nullable=False)
    win_count = db.Column(db.Integer())

    def to_dc(self):
        return User(**self.svalue)


@dataclass
class Score:
    id: int
    game_id: int
    user_id: int
    points: int
    user_attempts: int


class ScoreModel(db.Model):
    __tablename__ = "scores"

    id = db.Column(db.Integer(), primary_key=True)
    game_id = db.Column(db.ForeignKey("games.id"), nullable=False)
    user_id = db.Column(
        db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    points = db.Column(db.Integer(), nullable=False)
    user_attempts = db.Column(db.Integer(), nullable=False)

    def to_dc(self):
        return Score(**self.svalue)
