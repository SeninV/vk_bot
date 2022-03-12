from dataclasses import dataclass
from datetime import datetime
from typing import List
from sqlalchemy.sql import func
from enum import Enum
from app.store.database.gino import db


class GameStatus(Enum):
    START = "start"
    DURATION = "duration"
    DURATION_QUESTION = "duration_question"
    PLAYING = "playing"
    FINISH = "finish"

    def __str__(self):
        return str(self.value)

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(str(self))


@dataclass
class Game:
    id: int
    chat_id: int
    status: str
    start: datetime
    end: datetime
    duration_game: int
    duration_question: int
    theme_id: int
    unused_questions: List[int]


class GameModel(db.Model):
    __tablename__ = "games"

    id = db.Column(db.Integer(), primary_key=True)
    chat_id = db.Column(db.Integer(), nullable=False)
    status = db.Column(db.String(), nullable=False)
    start = db.Column(db.DateTime(), server_default=func.now())
    end = db.Column(db.DateTime(), server_default=func.now())
    duration_game = db.Column(db.Integer(), nullable=False)
    duration_question = db.Column(db.Integer(), nullable=False)
    theme_id = db.Column(db.Integer(), db.ForeignKey("themes.id", ondelete="CASCADE"))
    unused_questions = db.Column(db.ARRAY(db.Integer()))

    def to_dc(self):
        return Game(
            id=self.id,
            chat_id=self.chat_id,
            status=self.status,
            start=self.start,
            end=self.end,
            duration_game=self.duration_game,
            duration_question=self.duration_question,
            theme_id=self.theme_id,
            unused_questions=self.unused_questions,
        )


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
        return User(
            id=self.id,
            user_id=self.user_id,
            first_name=self.first_name,
            last_name=self.last_name,
            win_count=self.win_count,
        )


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
        return Score(
            id=self.id,
            game_id=self.game_id,
            user_id=self.user_id,
            points=self.points,
            user_attempts=self.user_attempts,
        )
