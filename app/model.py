import json
import uuid
from enum import Enum, IntEnum
from typing import List, Optional

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
        text("select id, name, leader_card_id from user where token=:token"),
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
        result = conn.execute(
            text(
                "update user set name = :name, leader_card_id = :leader where token = :token"
            ),
            {"name": name, "leader": leader_card_id, "token": token},
        )

# ------------------- ROOM MDOEL --------------------------

class LiveDifficulty(Enum):
     normal = 1
     hard = 2

class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4

class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3

class RoomInfo(BaseModel):
    room_id : int
    live_id : int
    joined_user_count : int
    max_user_count : int

class RoomUser(BaseModel):
    user_id : int
    name : str
    leader_card_id : int
    select_difficulty : int
    is_me : int
    is_host : int

class ResultUser(BaseModel):
    user_id : int
    judge_count_list : list[int]
    score : int


def create_room(token : str, live_id : int, select_difficulty : int) -> int:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO room (live_id, joined_user_count, max_user_count) VALUES (:live_id, :joined_user_count, :max_user_count)"
            ),
            {"live_id" : live_id, "joined_user_count" : 1, "max_user_count" : 4},
        )

        result = conn.execute(
            text(
                "select max(room_id) as room_id from room"
            )
        )

        roomId = result.one()
        user = _get_user_by_token(conn, token)

        conn.execute(
            text(
                "INSERT INTO room_member (room_id, user_id, is_host, select_difficulty) VALUES (:room_id, :user_id, :is_host, :select_difficulty)"
            ),
            {"room_id" : roomId.room_id, "user_id" : user.id, "is_host" : 1, "select_difficulty" : select_difficulty},
        )

    return roomId.room_id




def list_room(token : str, live_id : int) -> List[RoomInfo]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "select * from room"
            )
        )

    roomInfo : List[RoomInfo] = []

    try:
        row = result.one()
    except NoResultFound:
        return roomInfo

    for row in result:
        ri = RoomInfo()
        ri.room_id = row.room_id
        ri.live_id = row.live_id
        ri.joined_user_count = row.joined_user_count
        ri.max_user_count = row.max_user_count
        roomInfo.append(ri)

    return roomInfo


def join_room(token : str, room_id : int, select_difficulty : int) -> JoinRoomResult:

    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        result = conn.execute(
            text(
                "select count(*) as players from room_member where room_id = :room_id"
            ),
            {"room_id" : room_id}
        )

        try:
            row = result.one()
            if row.players >= 4:
                return JoinRoomResult.RoomFull
            elif row.players == 0:
                return JoinRoomResult.Disbanded
        except NoResultFound:
            return JoinRoomResult.OtherError

        conn.execute(
            text(
                "INSERT INTO room_member (room_id, user_id, is_host, select_difficulty) VALUES (:room_id, :user_id, :is_host, :select_difficulty)"
            ),
            {"room_id" : room_id, "user_id" : user.id, "is_host" : 0, "select_difficulty" : select_difficulty},
        )

    return JoinRoomResult.Ok
