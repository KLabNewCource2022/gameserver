from enum import Enum
from pydantic import BaseModel


class LiveDiffculty(Enum):
    '''難易度'''
    normal = 1
    hard = 2


class JoinRoomResult(BaseModel):
    '''加入するルームの状態'''
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(BaseModel):
    '''ルームの状態'''
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_diffculty: LiveDiffculty
    is_me: bool
    is_hose: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int

