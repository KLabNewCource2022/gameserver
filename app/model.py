from csv import unregister_dialect
import json
import struct
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

MAXUSERCNT = 4

class LiveDifficulty(Enum):
    Normal = 1
    Hard = 2

class JoinRoomResult(Enum):
    OK = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4

class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3

class RoomInfo(BaseModel):
    room_id:int
    live_id:int
    joined_user_count:int
    max_user_count:int

    class Config:
        orm_mode = True

class RoomUser(BaseModel):
    user_id:int
    name:str
    leader_card_id:int
    select_difficulty:LiveDifficulty
    is_me:bool
    is_host:bool

class ResultUser(BaseModel):
    user_id:int
    judge_count_list:list[int]
    score:int


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
        result = conn.execute(
            text(
                "UPDATE `user` SET `name`= :name, `leader_card_id` = :leader_card_id where `token` = :token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        return


def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text("INSERT INTO `room` (live_id, select_difficulty, status, owner) VALUE(:live_id,:select_difficulty,:status,:owner)"),
                {"live_id":live_id, "select_difficulty":select_difficulty.value, "status":WaitRoomStatus.Waiting.value, "owner":token},
            )
        # print(result)
    return result.lastrowid

def _list_room(conn,live_id:int)->list[Optional[RoomInfo]]:
        result = conn.execute(
            text("select * from `room` where `live_id` = :live_id"),
            {"live_id":live_id},
        )
        row = result.all()
        roomlists :list[RoomInfo]= []
        ri = RoomInfo()
        try:
            for i in row:
                ri.room_id = i.room_id
                ri.live_id = i.live_id
                ri.joined_user_count = 2#test
                ri.max_user_count = MAXUSERCNT
                roomlists.append(ri)
            return roomlists
        except NoResultFound:
            return
        

def list_room(live_id:int)->list[RoomInfo]:
    with engine.begin() as conn:
        roomlists = _list_room(conn,live_id)
        return roomlists
        

