from enum import Enum, IntEnum, auto

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import *

app = FastAPI()

# Sample APIs


@app.get("/")
async def root():
    return {"message": "Hello World"}


# User APIs


class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


class RoomCreateResquest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


class RoomListResquest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


class RoomStartRequest(BaseModel):
    room_id: int


class RoomStartResponse(BaseModel):
    pass


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


class RoomEndResponse(BaseModel):
    pass


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest):
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


bearer = HTTPBearer()


def get_auth_token(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(status_code=401, detail="invalid credential")
    return cred.credentials


@app.get("/user/me", response_model=SafeUser)
def user_me(token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=404)
    # print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# ルームを新規で建てる。
@app.post("/room/create", response_model=RoomCreateResponse)
def RoomCreate(req: RoomCreateResquest, token: str = Depends(get_auth_token)):
    room_id = model.create_room(
        token, live_id=req.live_id, select_difficulty=req.select_difficulty
    )
    return RoomCreateResponse(room_id=room_id)


# リストを返す
@app.post("/room/list", response_model=RoomListResponse)
def RoomList(req: RoomListResquest):
    infolist: list[RoomInfo] = find_room(req.live_id)

    print(infolist)
    return RoomListResponse(room_info_list=infolist)


# 部屋に入る
@app.post("/room/join", response_model=RoomJoinResponse)
def RoomJoin(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    result = try_join(
        room_id=req.room_id, token=token, select_difficulty=req.select_difficulty
    )
    return RoomJoinResponse(join_room_result=result)


# 待機
@app.post("/room/wait", response_model=RoomWaitResponse)
def RoomWait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    users = get_join_users(req.room_id, token)
    status = get_room_status(req.room_id)
    return RoomWaitResponse(status=status.value, room_user_list=users)


# スタート
@app.post("/room/start", response_model=RoomStartResponse)
def RoomStart(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    start_room(req.room_id, token)
    return RoomStartResponse()


# エンド
@app.post("/room/end", response_model=RoomEndResponse)
def RoomEnd(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    EndUser(req.room_id, req.judge_count_list, req.score, token)
    return RoomEndResponse()


# リザルト
@app.post("/room/result", response_model=RoomResultResponse)
def RoomResult(req: RoomResultRequest):
    result_users = get_result(req.room_id)
    return RoomResultResponse(result_user_list=result_users)
