import json
import string
import uuid
from enum import Enum, IntEnum
from typing import Any, List, Optional

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

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: int
    is_me: int
    is_host: int

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int

    class Config:
        orm_mode = True


def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty) -> int:
    with engine.begin() as conn:
        # create new room
        result = conn.execute(
            text(
                "INSERT INTO room (live_id, started, joined_user_count, max_user_count) VALUES (:live_id, :started, :joined_user_count, :max_user_count)"
            ),
            {
                "live_id": live_id,
                "started": 0,
                "joined_user_count": 1,
                "max_user_count": 4,
            },
        )

        roomId = result.lastrowid

        # insert new row into room_member as host
        user = _get_user_by_token(conn, token)
        conn.execute(
            text(
                "INSERT INTO room_member (room_id, user_id, is_host, select_difficulty) VALUES (:room_id, :user_id, :is_host, :select_difficulty)"
            ),
            {
                "room_id": roomId,
                "user_id": user.id,
                "is_host": 1,
                "select_difficulty": select_difficulty.value
            },
        )

    return roomId


def list_room(live_id: int) -> List[RoomInfo]:
    # get all rooms
    with engine.begin() as conn:
        result: Any
        if live_id == 0:
            result = conn.execute(text("select * from room where started = 0"))
        else:
            result = conn.execute(text("select * from room where live_id = :live_id and started = 0"), {"live_id": live_id})

    # populate array with every active room and return it
    roomInfo: List[RoomInfo] = []
    try:
        for row in result:
            ri = RoomInfo(
                room_id=row.room_id,
                live_id=row.live_id,
                joined_user_count=row.joined_user_count,
                max_user_count=row.max_user_count,
            )
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
            text("select started from room where room_id = :room_id"),
            {"room_id": room_id},
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
            {"room_id": room_id},
        )

        # init user list    
        user_list: list[RoomUser] = []
        my_id = _get_user_by_token(conn, token).id
        try:
            for row in result_user:
                me = 1 if my_id == row.id else 0
                u = RoomUser(
                    user_id=row.id,
                    name=row.name,
                    leader_card_id=row.leader_card_id,
                    select_difficulty=row.select_difficulty,
                    is_me=me,
                    is_host=row.is_host,
                )
                user_list.append(u)
        except NoResultFound:
            return waitStatus, user_list

    return waitStatus, user_list


def start_room(token: str, room_id: int):
    with engine.begin() as conn:
        # start room, set started = 1
        conn.execute(
            text("update room set started = 1 where room_id = :room_id"),
            {"room_id": room_id},
        )


def end_room(token: str, room_id: int, judge_count_list: list[int], score: int):
    with engine.begin() as conn:
        # save scores into room_member
        user_id = _get_user_by_token(conn, token).id
        judges = ",".join(list(map(str, judge_count_list)))
        conn.execute(
            text(
                "update room_member set judge_count_list = :judge_count_list, score = :score where room_id = :room_id and user_id = :user_id"
            ),
            {
                "judge_count_list": judges,
                "score": score,
                "room_id": room_id,
                "user_id": user_id,
            },
        )


def result_room(room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        # check if every player in room is done playing
        result = conn.execute(
            text(
                "select score from room_member where room_id = :room_id"
            ),
            {"room_id": room_id},
        )

        try:
            for row in result:
                if row.score is None:
                    return []
        except NoResultFound:
            pass

        # get scores from users
        result = conn.execute(
            text(
                "select user_id, judge_count_list, score from room_member where room_id = :room_id"
            ),
            {"room_id": room_id}
        )

        user_list: list[ResultUser] = []
        try:
            for row in result:
                strlist = row.judge_count_list.split(",")
                judges = [int(x) for x in strlist]
                u = ResultUser(
                    user_id=row.user_id, judge_count_list=judges, score=row.score
                )
                user_list.append(u)
        except NoResultFound:
            return user_list

        return user_list


def leave_room(token: str, room_id: int) -> None:
    with engine.begin() as conn:
        user_id = _get_user_by_token(conn, token).id
        # check if user is host
        result = conn.execute(
            text(
                "select is_host from room_member where room_id=:room_id and user_id=:user_id"
            ),
            {"room_id": room_id, "user_id": user_id},
        )

        # if player is host, remove every player and disband room
        if result.one().is_host == 1:
            conn.execute(
                text("delete from room_member where room_id=:room_id"),
                {
                    "room_id": room_id,
                },
            )
            conn.execute(
                text("delete from room where room_id=:room_id"),
                {
                    "room_id": room_id,
                },
            )

            return

        # remove this user from room_member
        conn.execute(
            text(
                "delete from room_member where room_id=:room_id and user_id = :user_id"
            ),
            {"room_id": room_id, "user_id": user_id},
        )
