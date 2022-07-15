import http
from sqlalchemy import text
from app.db import engine
import random

from fastapi import HTTPException
from app.model import SafeUser
from . import common
from sqlalchemy.exc import NoResultFound


def create_room(live_id: int, select_difficully: common.LiveDiffculty, owner:SafeUser) -> common.RoomCreateResponse:
    room_id = random.randint(0, 1000000)
    with engine.begin() as conn:
        create_result = conn.execute(
            text("INSERT INTO `room` (room_id, live_id, joined_user_count,max_user_count,status,owner_id) VALUES(:room_id, :live_id,:joined_user_count,:max_user_count,:status,:owner_id)"),
            {"room_id": room_id, "live_id": live_id ,"joined_user_count": 1,"max_user_count":4,"status":1,"owner_id":owner.id},
        )
        join_result = conn.execute(
            text("INSERT INTO `room_user` (room_id,user_id,name,leader_card_id,select_difficulty,is_me,is_host) VALUES(:room_id,:user_id,:name,:leader_card_id,:select_difficulty,:is_me,:is_host)"),
            {"room_id":room_id,"user_id":owner.id,"name":owner.name,"leader_card_id":owner.leader_card_id,"select_difficulty":int(common.LiveDiffculty(select_difficully)),"is_me":True,"is_host":True}
        )
        delete_userscore = conn.execute(
            text("delete from `user_score` where `user_id`=:user_id"),
            {"user_id":owner.id}
        )
    return common.RoomCreateResponse(room_id=room_id)


def list_room(live_id: int) -> common.RoomListResponse:
    rooms_info = []
    with engine.begin() as conn:
        if live_id != 0:
            result = conn.execute(
                text("SELECT `room_id`, `live_id`, `joined_user_count` , `status`,`owner_id`,`max_user_count` FROM `room` WHERE `live_id`=:live_id and `status`=1 and `joined_user_count`<4"),
                {"live_id": live_id},
            )
        elif live_id == 0:
            result = conn.execute(
                text("SELECT `room_id`, `live_id`, `joined_user_count`, `status`,`owner_id`,`max_user_count` FROM `room` where `status`=1 and `joined_user_count`<4"),
                {},
            )
        try:
            rooms_info = result.all()
        except NoResultFound:
            return None
    return common.RoomListResponse(room_info_list=rooms_info)


def join_room(room_id: int,select_difficulty:common.LiveDiffculty,user:SafeUser) -> common.RoomJoinResponse:
    with engine.begin() as conn:
        check_room_state = conn.execute(
            text("select `status` from `room` where room_id=:room_id"),
            {"room_id":room_id}
        )
        room_state = check_room_state.one().status
        if room_state != 1:
            return common.RoomJoinResponse(join_room_result=room_state)
        room_user_result = conn.execute(
            text("INSERT INTO `room_user` (room_id,user_id,name,leader_card_id,select_difficulty,is_me,is_host) VALUES(:room_id,:user_id,:name,:leader_card_id,:select_difficulty,:is_me,:is_host)"),
            {"room_id":room_id,"user_id":user.id,"name":user.name,"leader_card_id":user.leader_card_id,"select_difficulty":int(common.LiveDiffculty(select_difficulty)),"is_me":True,"is_host":False}
        )
        room_result = conn.execute(
            text("update `room` set `joined_user_count`= `joined_user_count`+1 where room_id=:room_id"),
            {"room_id":room_id}
        )
        delete_userscore = conn.execute(
            text("delete from `user_score` where `user_id`=:user_id"),
            {"user_id":user.id}
        )
        pass
    return common.RoomJoinResponse(join_room_result=1)


def wait_room(room_id: int) -> common.RoomWaitResponse:
    users = []
    with engine.begin() as conn:
        result = conn.execute(
            text("select `user_id`,`name`,`leader_card_id`,`select_difficulty`,`is_me`,`is_host` from `room_user` where `room_id`=:room_id"),
            {"room_id": room_id},
        )
        room_result = conn.execute(
            text("select `status` from `room` where `room_id`=:room_id"),
            {"room_id":room_id},
        )
        try:
            users = result.all()
        except NoResultFound:
            return None
        finally:
            room_status = room_result.all()
            state = int(room_status[0].status)
    return common.RoomWaitResponse(status=state, room_user_list=users)


def start_room(room_id:int,user:SafeUser) -> None:
    with engine.begin() as conn:
        result = conn.execute(
            text("update `room` set `status`=2 WHERE `room_id`=:room_id"),
            {"room_id":room_id}
        )
    return None


def end_room(room_id:int ,judge_count_list:list[int],score:int, user:SafeUser)->None:
    with engine.begin() as conn:
        result = conn.execute(
            text("insert into `user_score` (user_id,perfect,great,good,bad,miss,score,room_id) VALUES(:user_id,:perfect,:great,:good,:bad,:miss,:score,:room_id) "),
            {"user_id":user.id,"perfect":judge_count_list[0],"great":judge_count_list[1],"good":judge_count_list[2],"bad":judge_count_list[3],"miss":judge_count_list[4],"score":score,"room_id":room_id},
        )
        close_room = conn.execute(
            text("delete from `room` where `room_id`=:room_id"),
            {"room_id":room_id}
        )
        delete_roomuser = conn.execute(
            text("delete from `room_user` where `user_id`=:user_id"),
            {"user_id":user.id}
        )
    return None


def result_room(room_id: int) -> common.RoomResultResponse:
    result_user_list = []
    with engine.begin() as conn:
        room_user_result = conn.execute(
            text("select `user_id`,`perfect`,`great`,`good`,`bad`,`miss`,`score` from `user_score` where `room_id`=:room_id"),
            {"room_id": room_id}
        )
        rows = room_user_result.all()
        for row in rows:
            result_user_list.append(common.ResultUser(user_id=row.user_id,judge_count_list=[row.perfect,row.great,row.good,row.bad,row.miss],score=row.score))
    return common.RoomResultResponse(result_user_list=result_user_list)


def leave_room(room_id:int,user:SafeUser) -> None:
    with engine.begin() as conn:
        room_useramount = conn.execute(
            text("select `joined_user_count`,`owner_id` from `room` where `room_id`=:room_id"),
            {"room_id":room_id}
        )
        # is owner
        if room_useramount.one()["owner_id"] == user.id:
            close_room = conn.execute(
                text("update `room` set `status`=3 WHERE `room_id`=:room_id"),
                {"room_id":room_id}
            )
            delete_all_room_user = conn.execute(
                text("delete from `room_user` where `room_id`=:room_id"),
                {"room_id":room_id}
            )
            delete_room = conn.execute(
                text("delete from `room` where `room_id`=:room_id"),
                {"room_id":room_id}
            )
        # not owner
        else:
            delete_room_user = conn.execute(
                text("delete from `room_user` where `user_id`=:user_id"),
                {"user_id":user.id}
            )
            update_room_user_amount = conn.execute(
                text("update `room` set `joined_user_count`= `joined_user_count`-1 where room_id=:room_id"),
                {"room_id":room_id}
            )
    return None