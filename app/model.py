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

class WaitRoomStatus(IntEnum):
    """test"""
    WAITING = 1
    LIVE_START = 2
    DISSOLUTION = 3

# db用

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

def _create_room_member(conn, room_id: int, user_id: int, select_difficulty: LiveDifficulty):
        conn.execute(
            text(
                "INSERT INTO `room_member` (`room_id`, `user_id`, `select_difficulty`) VALUES (:room_id, :user_id, :select_difficulty)"
            ),
            dict(room_id=room_id, user_id=user_id, select_difficulty=int(select_difficulty))
        )

def _get_room(conn, room_id: int):
    room_result = conn.execute(
        text("SELECT * FROM `room` WHERE id = :room_id"),
        dict(room_id=room_id)
    )

    return room_result.one()


def create_room(live_id: int, select_difficulty: LiveDifficulty, token: str) -> int:
    user = get_user_by_token(token)
    with engine.begin() as conn:
        # もっと楽に取れそう
        conn.execute(
            text(
                "INSERT INTO `room` (live_id, wait_room_status, created_by) VALUES (:live_id, :wait_room_status, :created_by)"
            ),
            dict(live_id=live_id,  wait_room_status=int(WaitRoomStatus.WAITING), created_by=user.id)
        )
        result = conn.execute(
            text("SELECT `id` FROM room ORDER BY id DESC LIMIT 1")
        )
        room = result.one()
        # 作成したらホストは強制的にJoin
        _create_room_member(conn, room.id, user.id, select_difficulty)
    return room.id

def get_room_info_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        rooms_result = conn.execute(
            text("SELECT * FROM `room` WHERE `live_id` = :live_id ORDER BY `id`"),
            dict(live_id=live_id)
        )
        rooms = rooms_result.all()

        room_member_cnt_result = conn.execute(
            text(
                """
                SELECT room_id, COUNT(id) as member_cnt FROM `room_member`
                WHERE `room_id` IN (SELECT `id` FROM `room` WHERE `live_id` = :live_id)
                GROUP BY `room_id`
                ORDER BY `room_id`
                """
            ),
            dict(live_id=live_id)
        )
        room_member_cnt = room_member_cnt_result.all()

        rooms_info = []
        for room, member_cnt in zip(rooms, room_member_cnt):
            rooms_info.append(RoomInfo(
                room_id=room.id,
                live_id=room.live_id,
                joined_user_count=member_cnt.member_cnt,
                max_user_count=4
            ))

        return rooms_info

def join_room(room_id: int, select_difficulty: LiveDifficulty, token: str) -> JoinRoomResult:
    with engine.begin() as conn:
        room = _get_room(conn, room_id)

        if room.can_join:
            user = _get_user_by_token(conn, token)
            _create_room_member(conn, room_id, user.id, select_difficulty)

            room_member_cnt_result = conn.execute(
                text(
                    """
                    SELECT COUNT(id) as member_count FROM `room_member`
                    GROUP BY `room_id`
                    HAVING `room_id` = :room_id
                    """
                ),
                dict(room_id=room_id)
            )
            room_user_count = room_member_cnt_result.one()

            if room_user_count.member_count >= room.max_user_count:
                conn.execute(
                    text("UPDATE `room` SET `can_join` = :can_join WHERE `id` = :id"),
                    dict(can_join=False, id=room_id)
                )

        return room.room_status

def room_polling(room_id: int, token: str) -> tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        room = _get_room(conn, room_id)

        room_members_result = conn.execute(
            text("SELECT user_id, select_difficulty FROM room_member WHERE room_id = :room_id"),
            dict(room_id=room_id)
        )
        room_members = room_members_result.all()

        request_user = _get_user_by_token(conn, token)
        room_user_list = []
        for room_member in room_members:
            user_result = conn.execute(
                text("SELECT name, leader_card_id FROM user WHERE id = :user_id"),
                dict(user_id=room_member.user_id)
            )
            user = user_result.one()
            room_user_list.append(RoomUser(
                user_id=room_member.user_id,
                name=user.name,
                leader_card_id=user.leader_card_id,
                select_difficulty=room_member.select_difficulty,
                is_me=(request_user.id == room_member.user_id),
                is_host=(room.created_by == room_member.user_id),
            ))
        
        return room.room_status, room_user_list

def start_room(room_id: int, token: str):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return
        # ホストチェック
        room = _get_room(conn, room_id)
        if room.created_by != user.id:
            raise HTTPException(status_code=403, detail="Requests from non-host user.")

        conn.execute(
            text("UPDATE room SET `room_status` = :room_status WHERE `id` = :room_id"),
            dict(room_status=int(WaitRoomStatus.LIVE_START), room_id=room_id),
        )

def end_room(room_id: int, judge_count_list: list[int], score: int, token: str):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return

        perfect = judge_count_list[0]
        great = judge_count_list[1]
        good = judge_count_list[2]
        bad = judge_count_list[3]
        miss = judge_count_list[4]
        score_id = conn.execute(
            text(
                """
                INSERT INTO `score` (`score`, `perfect`, `great`, `good`, `bad`, `miss`)
                VALUES (:score, :perfect, :great, :good, :bad, :miss)
                """
            ),
            dict(score=score, perfect=perfect, great=great, good=good, bad=bad, miss=miss)
        ).lastrowid

        print(score_id)
        
        conn.execute(
            text("UPDATE `room` SET `room_status` = :room_status, `score_id` = :score_id WHERE `id` = :room_id"),
            dict(room_status=int(WaitRoomStatus.DISSOLUTION), score_id=score_id, room_id=room_id),
        )
