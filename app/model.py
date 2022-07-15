from ctypes import Union
import json
from os import stat
from tkinter import N
from unittest import result
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class LiveDifficulty(IntEnum):
    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
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
    is_me: bool
    is_host: bool

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


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
        conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    pass


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        conn.execute(
            text(
                "update `user` set `name`= :name, `leader_card_id`= :leader_card_id where `token`= :token"
            ),
            dict(name=name, leader_card_id=leader_card_id, token=token)
        )


def insert_room(token: str, live_id: int, select_difficulty: int, max_user_count: int) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "insert into `room` (owner_token, live_id, select_difficulty, max_user_count) values (:owner_token, :live_id, :select_difficulty, :max_user_count)"
            ),
            dict(owner_token=token, live_id=live_id, select_difficulty=select_difficulty, max_user_count=max_user_count)
        )
        return result.lastrowid


def get_enterable_room_list(live_id: int) -> list[RoomInfo]:
    
    with engine.begin() as conn:
        query: str = "select * from `room` where `joined_user_count` < `max_user_count`" if live_id == 0 else "select * from `room` where `live_id` = :live_id and `joined_user_count` < `max_user_count`"
        result = conn.execute(
            text(
                query
            ),
            dict(live_id=live_id)
        )
        room_info_list: list[RoomInfo] = []
        for item in result.all():
            room_info_list.append(RoomInfo(room_id=item.id, live_id=item.live_id, joined_user_count=item.joined_user_count, max_user_count=item.max_user_count))
        
        print(room_info_list)
    return room_info_list


def join_selected_room(token: str, room_id: int, select_difficulty: LiveDifficulty) -> JoinRoomResult:

    with engine.begin() as conn:
        # Todo disbunded

        # Check Error
        result_room_condition = conn.execute(
            text(
                "select id, joined_user_count, max_user_count, status from `room` where `id` = :id and `select_difficulty` = :select_difficulty"
            ),
            dict(id=room_id, select_difficulty=select_difficulty)
        )
        
        room_conditions = result_room_condition.all()
        if room_conditions is None:
            return JoinRoomResult.OtherError

        room_empty_list = [condition.joined_user_count < condition.max_user_count for condition in room_conditions]
        if not any(room_empty_list):
            return JoinRoomResult.RoomFull

        room_disbanded_list = [condition.status == WaitRoomStatus.Waiting for condition in room_conditions]
        if not any(room_disbanded_list):
            return JoinRoomResult.Disbanded

        vaild_index = 0
        for i in range(len(room_conditions)):
            if room_empty_list[i] and room_disbanded_list[i]:
                vaild_index = i

        # OK
        conn.execute(
            text(
                "update `room` set `joined_user_count` = `joined_user_count` + 1 where `id` = :id" 
            ),
            dict(id=room_conditions[vaild_index].id)
        )
        result_user = conn.execute(
            text(
                "select id from `user` where `token` = :token"
            ),
            dict(token=token)
        )
        user = result_user.one()
        if user is None:
            return JoinRoomResult.OtherError

        conn.execute(
            text(
                "insert into `room_user` ( room_id, user_id, select_difficulty) values (:room_id, :user_id, :select_difficulty)"
            ),
            dict(room_id=room_conditions[vaild_index].id, user_id=user.id, select_difficulty=select_difficulty)
        )
        return JoinRoomResult.Ok


def wait_selected_room(token: str, room_id: int):
    
    with engine.begin() as conn:
        
        # room status
        result_room = conn.execute(
            text(
                "select status, owner_token from `room` where `id`=:id"
            ),
            dict(id=room_id)
        )
        room = result_room.one()
        if room is None:
            return

        # room user
        result_room_user_list = conn.execute(
            text(
                "select room_user.user_id, room_user.select_difficulty, user.token, user.name, user.leader_card_id from `room_user` inner join `user` on room_user.user_id = user.id where `room_id` = :room_id"
            ),
            dict(room_id=room_id)
        )
        room_user_list = result_room_user_list.all()
        if room_user_list is None:
            return

        # mapping RoomUser
        list_room_user: list[RoomUser] = []
        for item in room_user_list:
            list_room_user.append(RoomUser(user_id=item.room_user.user_id, name=item.user.name, leader_card_id=item.user.leader_card_id, select_difficulty=item.room_user.select_difficulty, is_me=True if token == item.user.token else False, is_host=True if token == room.owner_token else False))
        
        print(list_room_user)
        return (room.status, list_room_user)


