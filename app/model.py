import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        dict(token=token),
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        # 対象ユーザーがいない場合アップデート処理しない
        if user is None:
            return
        conn.execute(
            text(
                "UPDATE user SET `name` = :name, `leader_card_id` = :leader_card_id WHERE `id` = :id"
            ),
            dict(name=name, leader_card_id=leader_card_id, id=user.id),
        )

# room周り

# enum

class LiveDifficulty(IntEnum):
    NORMAL = 1
    HARD = 2

class JoinRoomResult(IntEnum):
    OK = 1
    ROOM_FULL = 2
    DISBANDED = 3
    OTHER_ERROR = 4

class WaitRoomStatus:
    WAITING = 1
    LIVE_START = 2
    DISSOLUTION = 3

class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int

    class Config:
        orm_mode = True

class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool

    class Config:
        orm_mode = True

class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int

    class Config:
        orm_mode = True

def create_room(live_id: int, select_difficulty: LiveDifficulty, token: str) -> int:
    user = get_user_by_token(token)
    with engine.begin() as conn:
        # もっと楽に取れそう
        conn.execute(
            text(
                "INSERT INTO `room` (live_id, select_difficulty, wait_room_status, created_by) VALUES (:live_id, :select_difficulty, :wait_room_status, :created_by)"
            ),
            dict(live_id=live_id, select_difficulty=int(select_difficulty), wait_room_status=WaitRoomStatus.WAITING, created_by=user.id)
        )
        result = conn.execute(
            text(
                "SELECT `id` FROM room ORDER BY id DESC LIMIT 1"
            )
        )
    return result.one().id
