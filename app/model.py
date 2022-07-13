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

class Room(BaseModel):
    id: int
    live_id: int

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
    except:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        # user = _get_user_by_token(token)

        result = conn.execute(
            text(
                "UPDATE `user` SET `name`=:name , `leader_card_id`=:leader_card_id WHERE `token`=:token"
            ),
            dict(token=token, name=name, leader_card_id=leader_card_id),
        )


def create_room(token: str, live_id:int, select_difficulty:int) -> Room:
    with engine.begin() as conn:
        #ユーザid取得
        user_id = _get_user_by_token(conn=conn,token=token).id
        #部屋作成
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id) VALUES (:live_id);SELECT * from room where id = LAST_INSERT_ID()"
            ),
            {"live_id": live_id},
        )
        #部屋名取得
        try:
            row = result.one()
            print(f"{row}aaaaaaaaaaaaaaaaa")
        except:
            print(f"{row}aaaaaaaaaaaaaaaaa")
            return None
        room = Room.from_orm(row)

        result = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id , user_id , select_difficulty) VALUES (:room_id ,:user_id ,:select_difficulty)"
            ),
            {"room_id": room.id,"user_id":user_id,"select_difficulty":select_difficulty},
        )

        return room.id