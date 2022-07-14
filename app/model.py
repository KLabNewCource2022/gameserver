import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

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
        text("select id,name,leader_card_id from user where token=:token"),
        {"token": token},
    )
    try:
        return SafeUser.from_orm(result.one())
    except NoResultFound:
        return None


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise Exception("invalid user token")
        conn.execute(
            text("update user set name=:name, leader_card_id=:leader where id=:id"),
            {"name": name, "leader": leader_card_id, "id": user.id},
        )


class WaitRoomStatus(IntEnum):
    waiting = 1
    live_start = 2
    dissolution = 3


class LiveDifficulty(IntEnum):
    normal = 1
    hard = 2


def create_room(token: str, live_id: int, difficulty: LiveDifficulty) -> int:
    with engine.begin() as conn:
        owner = _get_user_by_token(conn, token)
        if owner is None:
            raise Exception("invalid user token")

        result = conn.execute(
            text(
                "insert into room (live_id, owner, status, member_count) values (:live_id, :owner, :status, 1)"
            ),
            {
                "live_id": live_id,
                "owner": owner.id,
                "status": WaitRoomStatus.waiting.value,
            },
        )
        room_id = result.lastrowid

        result = conn.execute(
            text(
                "insert into room_member set room_id=:room_id, user_id=:user_id, difficulty=:difficulty"
            ),
            {"room_id": room_id, "user_id": owner.id, "difficulty": difficulty.value},
        )

        return room_id


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


def list_rooms(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(
                text(
                    "select id,live_id,member_count from room where status=1 and member_count<4"
                )
            )
        else:
            result = conn.execute(
                text(
                    "select id,live_id,member_count from room where status=1 and member_count<4 and live_id=:live_id"
                ),
                {"live_id": live_id},
            )

        roomlist = []
        for row in result:
            room = RoomInfo(
                room_id=row.id,
                live_id=row.live_id,
                joined_user_count=row.member_count,
                max_user_count=4,
            )
            roomlist.append(room)
        return roomlist
