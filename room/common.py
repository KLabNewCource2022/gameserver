from enum import Enum
from pydantic import BaseModel


class LiveDiffculty(int, Enum):
    '''難易度'''
    normal = 1
    hard = 2


class JoinRoomResult(int, Enum):
    '''加入するルームの状態'''
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(int, Enum):
    '''ルームの状態'''
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int
    status: WaitRoomStatus
    owner_id: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDiffculty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDiffculty


class RoomCreateResponse(BaseModel):
    room_id: int


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDiffculty

    class Config:
        orm_mode = True


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult

    class Config:
        orm_mode = True


class RoomWaitRequest(BaseModel):
    room_id: int

    class Config:
        orm_mode = True


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]

    class Config:
        orm_mode = True


class RoomStartRequest(BaseModel):
    room_id: int

    class Config:
        orm_mode = True


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]

    class Config:
        orm_mode = True


class RoomLeaveRequest(BaseModel):
    room_id: int

    class Config:
        orm_mode = True