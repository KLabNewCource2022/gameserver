import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

# Enums


class LiveDifficulty(Enum):
    normal: int = 1
    hard: int = 2


class JoinRoomResult(Enum):
    OK: int = 1  # 入場OK
    RoomFull: int = 2  # 満員
    Disbanded: int = 3  # 解散済み
    OtherError: int = 4  # その他エラー


class WaitRoomStatus(Enum):
    Waiting: int = 1  # ホストがライブ開始ボタン押すのを待っている
    LiveStart: int = 2  # ライブ画面遷移OK
    Dissolution: int = 3  # 解散された


# Classes


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


class RoomInfo(BaseModel):
    room_id: int  # 部屋識別子
    live_id: int  # プレイ対象の楽曲識別子
    joined_user_count: int  # 部屋に入っている人数
    max_user_count: int  # 部屋の最大人数

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    user_id: int  # ユーザー識別子
    name: str  # ユーザー名
    leader_card_id: int  # 設定アバター
    select_difficulty: LiveDifficulty  # 選択難易度
    is_me: bool  # リクエスト投げたユーザーと同じか
    is_host: bool  # 部屋を立てた人か

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    user_id: int  # ユーザー識別子
    judge_count_list: list[int]  # 各判定数（良い判定から昇順）
    score: int  # 獲得スコア

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
        text("SELECT * FROM `user` WHERE token=:token"), {"token": token}
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
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader WHERE token=:token"
            ),
            {"token": token, "name": name, "leader": leader_card_id},
        )


def create_room(live_id: int, difficulty: LiveDifficulty) -> int:
    """ルームを作成する"""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, select_difficulty, max_user_count) VALUES (:live_id, :difficulty, 4)"
            ),
            {"live_id": live_id, "difficulty": difficulty.value},
        )
    return result.lastrowid


def find_room(live_id: int):
    """ルームを検索する"""
    with engine.begin() as conn:
        if live_id == 0:
            query_where = ""
        else:
            query_where = " where live_id=:live_id"

        result = conn.execute(
            text(
                "SELECT room_id, live_id, IFNULL(CC, 0) as joined_user_count, max_user_count FROM room LEFT OUTER JOIN (SELECT room_id as ID, COUNT(room_id) as CC FROM room_member GROUP BY room_id) as C on room_id = ID"
                + query_where
            ),
            {"live_id": live_id},
        )

        try:
            return result.all()
        except NoResultFound:
            return []


def join_room(room_id: int, difficulty: LiveDifficulty, token: str) -> JoinRoomResult:
    """ルームに入場する"""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT room_id, CC as joined_user_count, max_user_count FROM room LEFT OUTER JOIN (SELECT room_id as ID, COUNT(room_id) as CC FROM room_member WHERE room_id = :room_id GROUP BY room_id) as C on room_id = ID WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            row = result.one()
            if row.joined_user_count is None:
                # Note: create_room 直後は room_member にまだ追加されておらず joined_user_count is None となる
                # Nothing to do
                pass
            elif row.joined_user_count >= row.max_user_count:
                # 参加者数 >= 参加上限 : 満員
                return JoinRoomResult.RoomFull
            elif row.joined_user_count == 0:
                # 誰も参加していない : 解散済み
                return JoinRoomResult.Disbanded
        except NoResultFound:
            # クエリの結果が空 : その他エラー
            return JoinRoomResult.OtherError

        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, select_difficulty, token) VALUES (:room_id, :difficulty, :token)"
            ),
            {"room_id": room_id, "difficulty": difficulty.value, "token": token},
        )
        # 入場OK
        return JoinRoomResult.OK
