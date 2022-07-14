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
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: int
    is_me: int
    is_host: int


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


def create_room(token: str, live_id: int, select_difficulty: int) -> int:
    with engine.begin() as conn:
        # create new room
        conn.execute(
            text(
                "INSERT INTO room (live_id, started, joined_user_count, max_user_count) VALUES (:live_id, :started, :joined_user_count, :max_user_count)"
            ),
            {"live_id": live_id, "started": 0, "joined_user_count": 1, "max_user_count": 4},
        )

        # get the new room_id to return
        result = conn.execute(text("select max(room_id) as room_id from room"))

        roomId = result.one()

        # insert new row into room_member as host
        user = _get_user_by_token(conn, token)
        conn.execute(
            text(
                "INSERT INTO room_member (room_id, user_id, is_host, select_difficulty) VALUES (:room_id, :user_id, :is_host, :select_difficulty)"
            ),
            {
                "room_id": roomId.room_id,
                "user_id": user.id,
                "is_host": 1,
                "select_difficulty": select_difficulty,
            },
        )

    return roomId.room_id


def list_room(token: str, live_id: int) -> List[RoomInfo]:
    # get all active room
    with engine.begin() as conn:
        result = conn.execute(text("select * from room"))

    # populate array with every active room and return it
    roomInfo: List[RoomInfo] = []
    try:
        for row in result:
            ri = RoomInfo(room_id=row.room_id, live_id=row.live_id, joined_user_count=row.joined_user_count, max_user_count=row.max_user_count)
            roomInfo.append(ri)
    except NoResultFound:
        return roomInfo

    return roomInfo


def join_room(token: str, room_id: int, select_difficulty: int) -> JoinRoomResult:
    with engine.begin() as conn:
        # check if room can be joined
        user = _get_user_by_token(conn, token)
        result = conn.execute(
            text(
                "select count(*) as players from room_member where room_id = :room_id"
            ),
            {"room_id": room_id},
        )

        try:
            row = result.one()
            if row.players >= 4:
                return JoinRoomResult.RoomFull
            elif row.players == 0:
                return JoinRoomResult.Disbanded
        except NoResultFound:
            return JoinRoomResult.OtherError

        # join room (update the room_member table)
        conn.execute(
            text(
                "INSERT INTO room_member (room_id, user_id, is_host, select_difficulty) VALUES (:room_id, :user_id, :is_host, :select_difficulty)"
            ),
            {
                "room_id": room_id,
                "user_id": user.id,
                "is_host": 0,
                "select_difficulty": select_difficulty,
            },
        )

    return JoinRoomResult.Ok


def wait_room(token: str, room_id: int):
    with engine.begin() as conn:
        # get room status
        result_status = conn.execute(
            text(
                "select started from room where room_id = :room_id"
            ),
            {
                "room_id": room_id
            },
        )

        # init room wait status, return if disbanded
        waitStatus = WaitRoomStatus.Waiting
        try:
            if result_status.one().started == 1:
                waitStatus = WaitRoomStatus.LiveStart
        except NoResultFound:
            return WaitRoomStatus.Dissolution, []

        # get user list
        result_user = conn.execute(
            text(
                "select user.id, user.name, user.leader_card_id, room_member.select_difficulty, room_member.is_host from user right join room_member on user.id = room_member.user_id where room_id = :room_id"
            ),
            {
                "room_id": room_id
            },
        )

        # init user list
        user_list: list[RoomUser] = []
        my_id = _get_user_by_token(conn, token).id
        try:
            for row in user_list:
                me = 1 if my_id == row.id else 0
                u = RoomUser(user_id=row.id, name=row.name, leader_card_id=row.leader_card_id, select_difficulty=row.select_difficulty, is_me=me, is_host=row.is_host)
                user_list.append(u)
        except NoResultFound:
            return waitStatus, user_list

    return waitStatus, user_list
