from csv import unregister_dialect
import json
import struct
from unittest import result
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import false, text
from sqlalchemy.exc import NoResultFound

#from app.api import RoomWaitResponse

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
            text("INSERT INTO `room` (live_id, select_difficulty, status, joined_user_count, max_user_count, owner) VALUE(:live_id,:select_difficulty,:status,:joined_user_count,:max_user_count,:owner)"),
                {"live_id":live_id, "select_difficulty":select_difficulty.value, "status":WaitRoomStatus.Waiting.value, "joined_user_count":1, "max_user_count":MAXUSERCNT,"owner":token},
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
        try:
            for i in row:
                roomlists.append(
                RoomInfo(
                room_id = i.room_id,
                live_id = i.live_id,
                joined_user_count = i.joined_user_count,
                max_user_count = i.max_user_count
                ))
        except NoResultFound:
            return
        return roomlists
        

def list_room(live_id:int)->list[RoomInfo]:
    with engine.begin() as conn:
        roomlists = _list_room(conn,live_id)
        return roomlists
        
def join_room(token,room_id:int ,select_difficuty:LiveDifficulty)->JoinRoomResult:
    with engine.begin() as conn:
        result = conn.execute(text
        ("select `joined_user_count`,`max_user_count` from `room` where `room_id` =: room_id"),
        {"room_id":room_id},
        )
        try:
            row = result.one()
            if row.joined_user_count >= row.max_user_count:
                return JoinRoomResult.RoomFull.value
            if row.joined_user_count == 0:
                return JoinRoomResult.Disbanded.value
        except NoResultFound:
            return JoinRoomResult.OtherError.value
        
        user_by_token = _get_user_by_token(conn,token)
        result2 = conn.execute(text
        ("insert into `room_member` (`room_id`,`user_id`,`select_difficulty`,`is_owner`) value(:room_id,:user_id,:select_difficulty,:is_owner)"),
        {"room_id":room_id,"user_id":user_by_token.id,"select_difficulty":select_difficuty.value,"is_owner":false},
        )
        return JoinRoomResult.OK.value

def status_room(room_id:int)->WaitRoomStatus:
    with engine.begin() as conn:
        result = conn.execute(text
        ("select `status` from `room` where `room_id` =:room_id"),
        {"room_id":room_id}
        )
        row = result.one()
        return row.status

def user_list_room(token,room_id:int)->list[RoomUser]:
    with engine.begin() as conn:
        user_by_token = _get_user_by_token(conn,token)
        result = conn.execute(text
        ("select `user_id`, `select_difficulty`, `is_owner` from `room_member` where `room_id` = :room_id"),
        {"room_id":room_id}
        )
        row = result.all()
        room_user_list:list[RoomUser] = []
        for i in row:
            result2 = conn.execute(text
            ("select `name`, `leader_card_id` from `user` where `user_id`=:user_id"),
            {"user_id":i.user_id},
            )
            row2 = result2.one()

            if row.user_id == user_by_token.id: is_me = True
            else: is_me = False

            try:
                room_user_list.append(
                    RoomUser(
                        user_id = i.user_id,
                        name = row2.name,
                        leader_card_id = row2.leader_card_id,
                        select_difficulty = i.select_difficulty,
                        is_me = is_me,
                        is_host = i.is_owner
                    )
                )
            except NoResultFound:
                return
        return room_user_list

def start_room(token: str, room_id:str):
    with engine.begin() as conn:
        user_by_token = _get_user_by_token(conn,token)
        try:
            result = conn.execute(text
            ("select `owner` from `room` where `room_id`=:room_id"),
            {"room_id":room_id},
            )
        except NoResultFound:
            return
        row = result.one()
        if user_by_token.id == row.owner:
            conn.execute(text
            ("update `room` set `status`= :status where `room_id`=:room_id"),
            {"status":WaitRoomStatus.LiveStart.value,"room_id":room_id},
            )
        else:
            return

       