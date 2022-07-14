import json
import uuid
from enum import Enum, IntEnum
from typing import Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine
from .config import MAX_USER_COUNT
from .ResReqModel import (
    LiveDifficulty,
    ResultUser,
    WaitRoomStatus,
    JoinRoomResult,
    RoomInfo,
    RoomUser
)

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
    # TODO: 実装
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        {"token": token},
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
        # TODO: 実装
        try:
            _id = _get_user_by_token(conn, token).id
            conn.execute(
                text(
                    "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id WHERE id=:id"
                ),
                {"name": name, "leader_card_id": leader_card_id, "id": _id},
            )
        except NoResultFound:
            return None

def create_room(host_token:str, live_id:int, select_difficulty:LiveDifficulty):
    assert select_difficulty == LiveDifficulty.Normal or select_difficulty == LiveDifficulty.Hard
    with engine.begin() as conn:
        user_id = _get_user_by_token(conn, host_token).id
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, select_difficulty, status, member1, owner) VALUES (:live_id, :select_difficulty, :status, :member1, :member1)"
            ),
            {"live_id":live_id, "select_difficulty":select_difficulty.value, "status":WaitRoomStatus.Waiting.value, "member1":user_id},
        )
    return result.lastrowid

def _get_room_member_cnt_rom_room_by_live_id(conn, live_id:int) -> list[Optional[RoomInfo]]:
    try:
        result = conn.execute(
            text("SELECT * FROM `room` WHERE `live_id`=:live_id"),
            {"live_id": live_id}
        )
        rows = result.all()
        room_info_list = []
        for row in rows:
            room_status = WaitRoomStatus(row["status"])
            if room_status == WaitRoomStatus.Dissolution or room_status == WaitRoomStatus.LiveStart:
                continue
            joined_user_count = sum([1 if row[f"member{i}"] is not None else 0 for i in range(1,MAX_USER_COUNT + 1)])
            max_user_count = MAX_USER_COUNT
            room_info_list.append(
                RoomInfo(room_id=row["room_id"], live_id=row["live_id"],
                         joined_user_count=joined_user_count, max_user_count=max_user_count)
            )
        return room_info_list
    except NoResultFound:
        return None

def list_room(live_id:int) -> list[RoomInfo]:
    room_info_list = []
    with engine.begin() as conn:
        room_info_list = _get_room_member_cnt_rom_room_by_live_id(conn, live_id)
    return room_info_list

def _insert_new_member(conn, room_id:int, member_num:int, user_id:int) -> JoinRoomResult:
    try:
        conn.execute(
            text(f"UPDATE `room` SET `member{member_num}`=:member_id WHERE `room_id`=:room_id"),
            {"room_id": room_id, "member_id":user_id}
        )
        return JoinRoomResult.Ok
    except NoResultFound:
        return JoinRoomResult.OtherError

def _join_as_room_member(conn, room_id:int, token: str) -> int:
    try:
        user_id = _get_user_by_token(conn, token).id
        result = conn.execute(
            text("SELECT `member1`,`member2`,`member3`,`member4` FROM `room` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        row = result.one()
        members = [row[f"member{i}"] for i in range(1, MAX_USER_COUNT + 1) if row[f"member{i}"] is not None]
        absent_member_idx = [i for i in range(1, MAX_USER_COUNT + 1) if row[f"member{i}"] is None]
        joined_user_count = len(members)
        if joined_user_count == 0:
            # 解散
            return JoinRoomResult.Disbanded
        elif joined_user_count < MAX_USER_COUNT:
            if user_id not in members:
                # 空いてる席に追加
                return _insert_new_member(conn, room_id, absent_member_idx[0], user_id)
            else:
                return JoinRoomResult.Ok
        else:
            # RoomFull
            return JoinRoomResult.RoomFull
    except NoResultFound:
        return JoinRoomResult.OtherError

def join_room(room_id:int, token:str) -> int:
    with engine.begin() as conn:
        status = _join_as_room_member(conn, room_id, token)
    return status

def _get_user_info(conn, row, req_token) -> Tuple[WaitRoomStatus, list[RoomUser]]:
    user_info_list = []
    status = WaitRoomStatus(row["status"])
    host = row["owner"]
    select_difficulty = LiveDifficulty.Normal if row["select_difficulty"] == 1 else LiveDifficulty.Hard
    try:
        user_id_dict = {row[f"member{i}"]: i for i in range(1,MAX_USER_COUNT + 1) if row[f"member{i}"] is not None}
        if len(user_id_dict.values()) == 0:
            # Dissolution
            return status, []
        result = conn.execute(
            text("SELECT `id`, `name`, `leader_card_id`, `token` FROM `user` WHERE `id` IN :user_ids"),
            {"user_ids": list(user_id_dict.keys())}
        )
        member_rows = result.all()
        for row in member_rows:
            user_info_list.append(
                RoomUser(
                    user_id=row["id"], name=row["name"],
                    leader_card_id=row["leader_card_id"], select_difficulty=select_difficulty,
                    is_me=row["token"] == req_token,
                    # ここのホストの部分はよく考える必要がある
                    is_host=row["id"] == host
                )
            )
        return status, user_info_list
    except NoResultFound:
        return None

def _get_room_user_list(conn, room_id:str, token:str) -> Tuple[WaitRoomStatus, list[RoomUser]]:
    try:
        result = conn.execute(
            text("SELECT `member1`,`member2`,`member3`,`member4`, `select_difficulty`, `owner`, `status` FROM `room` WHERE `room_id`=:room_id"),
            {"room_id": room_id}
        )
        row = result.one()
        status, user_info_list = _get_user_info(conn, row, token)
        return status, user_info_list
    except NoResultFound:
        return None

def wait_room(room_id:int, token:str) -> Tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        status, room_user_list = _get_room_user_list(conn, room_id, token)
    return status, room_user_list

def _insert_room_into_result_table(conn, row):
    try:
        members = [f"member{i}" for i in range(1,1 + MAX_USER_COUNT) if row[f"member{i}"] is not None]
        inset_col = "room_id, member_num, " + ", ".join(members)
        inset_col_with_colon = ", ".join([":" + s for s in inset_col.split(', ')])
        value_dict = {s:row[s] for s in members}
        value_dict["room_id"] = row["room_id"]
        value_dict["member_num"] = len(members)
        result = conn.execute(
            text(
                f"INSERT INTO `result` ({inset_col}) VALUES ({inset_col_with_colon})"
            ), value_dict
        )
    except NoResultFound:
        return None


def start_room(room_id:int, token:str) -> None:
    with engine.begin() as conn:
        try:
            user_id = _get_user_by_token(conn, token).id
            result = conn.execute(
                text("SELECT `room_id`,`member1`,`member2`,`member3`,`member4`,`owner` FROM `room` WHERE `room_id`=:room_id"),
                {"room_id": room_id}
            )
            row = result.one()
            if user_id == row["owner"]:
                result = conn.execute(
                    text("UPDATE `room` SET `status`=:status WHERE `room_id`=:room_id"),
                    {"status": WaitRoomStatus.LiveStart.value, "room_id": room_id}
                )
                _insert_room_into_result_table(conn, row)
            else:
                print("owner is diffrent!!")
                raise Exception
        except NoResultFound as e:
            raise e

def _get_room_user_id_from_result(conn, room_id:int, token:str) -> int:
    try:
        user_id = _get_user_by_token(conn, token).id
        result = conn.execute(
            text("SELECT `member1`,`member2`,`member3`,`member4` FROM `result` WHERE `room_id`=:room_id"),
            {"room_id": room_id}
        )
        row = result.one()
        for i in range(1, 1 + MAX_USER_COUNT):
            if user_id == row[f"member{i}"]:
                return i
    except NoResultFound:
        return None
    return None

def _update_myresult_by_user_id(conn, room_id:int, user_id:int, score:int, judge_count_list:list[int]):
    try:
        judge_count_join = ", ".join(map(str,judge_count_list))
        conn.execute(
            text(
                f"UPDATE `result` SET score{user_id}=:score, judge_count_list{user_id}=:judge_count WHERE room_id=:room_id"
            ),
            {"room_id": room_id, "score": score, "judge_count":judge_count_join},
        )
    except NoResultFound:
        return None

def end_room(room_id:int, score:int, judge_count_list:list[int], token) -> None:
    with engine.begin() as conn:
        room_user_id = _get_room_user_id_from_result(conn, room_id, token)
        _update_myresult_by_user_id(conn, room_id, room_user_id, score, judge_count_list)

def check_can_return(row):
    member_num = row["member_num"]
    scores = [row[f"score{i}"] for i in range(1,MAX_USER_COUNT + 1) if row[f"score{i}"] is not None]
    return member_num != len(scores)

def _get_result_user_list_from_row(row) -> list[ResultUser]:
    if check_can_return(row):
        return []
    resultuser_list = []
    user_ids = [row[f"member{i}"] for i in range(1, MAX_USER_COUNT + 1) if row[f"score{i}"] is not None]
    scores = [row[f"score{i}"] for i in range(1,MAX_USER_COUNT + 1) if row[f"score{i}"] is not None]
    judge_count_lists = [row[f"judge_count_list{i}"].split(", ") for i in range(1,MAX_USER_COUNT + 1) if row[f"judge_count_list{i}"] is not None]
    judge_count_lists = [list(map(int, judge_count_list)) for judge_count_list in judge_count_lists]
    # sort
    # judge_count_lists = [sorted(judge_count_list) for judge_count_list in judge_count_lists]
    for u_id, score, judge_count_list in zip(user_ids, scores, judge_count_lists):
        resultuser_list.append(
            ResultUser(user_id=u_id, judge_count_list=judge_count_list, score=score)
        )
    return resultuser_list


def _get_result_user_list(conn, room_id) -> list[ResultUser]:
    try:
        result = conn.execute(
            text("SELECT * FROM `result` WHERE `room_id`=:room_id"),
            {"room_id": room_id}
        )
        row = result.one()
        return _get_result_user_list_from_row(row)
    except NoResultFound:
        return None

def result_room(room_id:int) -> None:
    with engine.begin() as conn:
        result_user_list = _get_result_user_list(conn, room_id)
    return result_user_list
