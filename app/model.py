import json
import uuid
from enum import Enum, IntEnum
from typing import Callable, Optional

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
                "INSERT INTO `user` "
                "(name, token, leader_card_id) "
                "VALUES (:name, :token, :leader_card_id)"
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
                "UPDATE `user` "
                "SET name = :name, leader_card_id = :leader "
                "WHERE token=:token"
            ),
            {"token": token, "name": name, "leader": leader_card_id},
        )


def _joined_room_id(conn, token: str) -> Optional[int]:
    result = conn.execute(
        text("SELECT room_id FROM room_member WHERE token = :token"),
        {"token": token},
    )
    row = result.one_or_none()
    if row is None:
        return None
    else:
        return row.room_id


def _delete_user_from_room_member(conn, room_id: int, token: str) -> None:
    conn.execute(
        text("DELETE FROM `room_member` WHERE room_id = :room_id AND token = :token"),
        {"room_id": room_id, "token": token},
    )


def _join_room(conn, room_id: int, difficulty: LiveDifficulty, token: str) -> None:
    joined_room_id = _joined_room_id(conn, token)
    if joined_room_id is not None:
        _delete_user_from_room_member(conn, joined_room_id, token)
    conn.execute(
        text(
            "INSERT INTO `room_member` "
            "(room_id, select_difficulty, token) "
            "VALUES (:room_id, :difficulty, :token)"
        ),
        {
            "room_id": room_id,
            "difficulty": difficulty.value,
            "token": token,
        },
    )


def create_room(live_id: int, token: str) -> int:
    """ルームを作成する"""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` "
                "(live_id, max_user_count, host_token) "
                "VALUES (:live_id, 4, :token)"
            ),
            {"live_id": live_id, "token": token},
        )
    return result.lastrowid


def create_room_and_join(live_id: int, difficulty: LiveDifficulty, token: str) -> int:
    """ルームを作成し、入室する"""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `room` "
                "(live_id, max_user_count, host_token) "
                "VALUES (:live_id, 4, :token)"
            ),
            {"live_id": live_id, "token": token},
        )
        room_id: int = result.lastrowid
        _join_room(conn, room_id, difficulty, token)
    return room_id


def find_room(live_id: int) -> list[RoomInfo]:
    """すべてのルームを検索する"""
    with engine.begin() as conn:
        query_where = " where started=0"
        if live_id != 0:
            query_where += " AND live_id=:live_id"

        result = conn.execute(
            text(
                "SELECT "
                "room_id, live_id, "
                "CC as joined_user_count, max_user_count "
                "FROM room "
                "LEFT OUTER JOIN ("
                "SELECT "
                "room_id as ID, "
                "COUNT(room_id) as CC "
                "FROM room_member GROUP BY room_id"
                ") as C on room_id = ID" + query_where
            ),
            {"live_id": live_id},
        )

        try:
            return [RoomInfo.from_orm(row) for row in result.all()]
        except NoResultFound:
            return []


def find_enable_room(live_id: int) -> list[RoomInfo]:
    """すべての有効な( = 解散されていない)ルームを検索する"""
    all_rooms: list[RoomInfo] = find_room(live_id)
    f: Callable[[RoomInfo], bool] = lambda x: x.joined_user_count > 0
    return [room_info for room_info in all_rooms if f(room_info)]


def find_joinable_room(live_id: int) -> list[RoomInfo]:
    """すべての入室可能なルームを検索する"""
    all_rooms: list[RoomInfo] = find_enable_room(live_id)
    f: Callable[[RoomInfo], bool] = lambda x: x.joined_user_count < x.max_user_count
    return [room_info for room_info in all_rooms if f(room_info)]


def join_room(room_id: int, difficulty: LiveDifficulty, token: str) -> JoinRoomResult:
    """ルームに入場する"""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT room_id, CC as joined_user_count, max_user_count "
                "FROM room LEFT OUTER JOIN ("
                "SELECT room_id as ID, COUNT(room_id) as CC "
                "FROM room_member WHERE room_id = :room_id GROUP BY room_id FOR UPDATE"
                ") as C on room_id = ID WHERE started=0 AND room_id=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            row = result.one()
            if row.joined_user_count is None:
                # Do not reached
                return JoinRoomResult.OtherError
            if row.max_user_count is None:
                # Do not reached
                return JoinRoomResult.OtherError

            if row.joined_user_count >= row.max_user_count:
                # 参加者数 >= 参加上限 : 満員
                return JoinRoomResult.RoomFull
            elif row.joined_user_count <= 0:
                # Do not reached
                return JoinRoomResult.OtherError
        except NoResultFound:
            # クエリの結果が空 : 既に部屋が閉じている
            # Note: ルーム側でライブが開始されている場合も「部屋が解散している」扱い
            return JoinRoomResult.Disbanded

        _join_room(conn, room_id, difficulty, token)
        # 入場OK
        return JoinRoomResult.OK


def room_status(room_id: int) -> WaitRoomStatus:
    """ルーム状態を取得する"""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT room_id, CC as joined_user_count, started "
                "FROM `room` LEFT OUTER JOIN ("
                "SELECT "
                "room_id as ID, "
                "COUNT(room_id) as CC "
                "FROM room_member WHERE room_id = :room_id GROUP BY room_id"
                ") as C on room_id = ID WHERE room_id = :room_id"
            ),
            {"room_id": room_id},
        )
        row = result.one()
        if row.joined_user_count == 0:
            return WaitRoomStatus.Dissolution
        elif row.started == b"\x01":
            return WaitRoomStatus.LiveStart
        else:
            return WaitRoomStatus.Waiting


def room_member(room_id: int, token: str) -> list[RoomUser]:
    """ルームにいるプレイヤー一覧を取得する"""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT "
                "*, id as user_id, "
                "(token = :token) as is_me, "
                "(token = host_token) as is_host "
                "FROM `user` INNER JOIN ("
                "SELECT room_id, token as t, select_difficulty "
                "FROM `room_member` "
                "WHERE room_id = :room_id AND score IS NULL"
                ") as M on token = t INNER JOIN ("
                "SELECT room_id as r, host_token FROM `room`"
                ") as R on room_id = r"
            ),
            {"token": token, "room_id": room_id},
        )
        try:
            return [RoomUser.from_orm(row) for row in result.all()]
        except NoResultFound:
            return []


def room_start_live(room_id: int) -> None:
    """ルームのライブを開始する"""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE `room` SET started = 1 WHERE room_id = :room_id"),
            {"room_id": room_id},
        )


def _is_room_all_member_send_result(conn, room_id: int) -> bool:
    result = conn.execute(
        text(
            "SELECT room_id, (COUNT(token) = COUNT(score)) as all_member_send "
            "FROM `room_member` "
            "WHERE room_id = :room_id "
            "GROUP BY room_id"
        ),
        {"room_id": room_id},
    )
    try:
        row = result.one()
        return row.all_member_send == 1
    except NoResultFound:
        return False


def _close_room(conn, room_id: int) -> None:
    conn.execute(
        text("DELETE FROM room WHERE room_id = :room_id"),
        {"room_id": room_id},
    )


def set_room_user_result(
    room_id: int, judge_count_list: list[int], score: int, token: str
) -> None:
    """リザルトを記録する"""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `room_member` "
                "SET score = :score, judge_count_list = :judges "
                "WHERE room_id = :room_id AND token = :token"
            ),
            {
                "room_id": room_id,
                "score": score,
                "judges": ",".join(str(i) for i in judge_count_list),
                "token": token,
            },
        )
        if _is_room_all_member_send_result(conn, room_id):
            _close_room(conn, room_id)


def room_member_result(room_id: int) -> list[ResultUser]:
    """ルームにいるプレイヤーのリザルト一覧を取得する"""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT user_id, judge_count_list, score, token "
                "FROM `room_member` INNER JOIN ("
                "SELECT id as user_id, token as t FROM user"
                ") as U ON token = t "
                "WHERE room_id = :room_id"
            ),
            {"room_id": room_id},
        )
        try:
            # まだプレイ中のユーザーがいるならリザルトは返さない
            rows = result.all()
            if len([None for row in rows if row.score is None]) > 0:
                return []
            return [
                ResultUser(
                    user_id=row.user_id,
                    judge_count_list=[int(s) for s in row.judge_count_list.split(",")],
                    score=row.score,
                )
                for row in rows
            ]
        except NoResultFound:
            return []


def _is_user_host(conn, room_id: int, token: str) -> bool:
    result = conn.execute(
        text(
            "SELECT host_token FROM `room` "
            "WHERE room_id = :room_id AND host_token = :token"
        ),
        {"room_id": room_id, "token": token},
    )
    row = result.one_or_none()
    return row is not None


def _find_first_room_client_user(conn, room_id: int, token: str) -> Optional[str]:
    result = conn.execute(
        text(
            "SELECT token FROM `room_member` "
            "WHERE room_id = :room_id AND token != :token"
        ),
        {"room_id": room_id, "token": token},
    )
    try:
        return result.one().token
    except NoResultFound:
        return None


def _set_user_host(conn, room_id: int, token: str) -> None:
    conn.execute(
        text("UPDATE `room` SET host_token = :token WHERE room_id = :room_id"),
        {"room_id": room_id, "token": token},
    )


def leave_room(room_id: int, token: str) -> None:
    """ルームから退場する"""
    with engine.begin() as conn:
        is_host = _is_user_host(conn, room_id, token)
        _delete_user_from_room_member(conn, room_id, token)
        if is_host:
            next_host_token: Optional[str] = _find_first_room_client_user(
                conn, room_id, token
            )
            if next_host_token is not None:
                _set_user_host(conn, room_id, next_host_token)
            else:
                _close_room(conn, room_id)
