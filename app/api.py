from email.mime import base
from enum import Enum
from lib2to3.pytree import Base
from ntpath import join
from telnetlib import STATUS

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import JoinRoomResult, LiveDifficulty, RoomInfo, RoomUser, SafeUser

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


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: int


class RoomCreateResponse(BaseModel):
    room_id: int


@app.post("/room/create", response_model=RoomCreateResponse)
def cretate_room(req: RoomCreateRequest, token: str = Depends(get_auth_token)):

    room_id: int = model.insert_room(token, req.live_id, req.select_difficulty, 1)
    return RoomCreateResponse(room_id=room_id)


class RoomGetListRequest(BaseModel):
    live_id: int


class RoomGetListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@app.post("/room/list", response_model=RoomGetListResponse)
def get_room_list(req: RoomGetListRequest, token: str = Depends(get_auth_token)):
    room_info_list: list[RoomInfo] = model.get_enterable_room_list(req.live_id)
    return RoomGetListResponse(room_info_list=room_info_list)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: int


class RoomJoinResponse(BaseModel):
    join_room_result: int


@app.post("/room/join", response_model=RoomJoinResponse)
def join_room(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    join_room_result: JoinRoomResult = model.join_selected_room(token, req.room_id, req.select_difficulty)
    return RoomJoinResponse(join_room_result=int(join_room_result))


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: int
    room_user_list: list[RoomUser]


@app.post("/room/wait", response_model=RoomWaitResponse)
def wait_room(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    res = model.wait_selected_room(token, req.room_id)
    return RoomWaitResponse(res[0], res[1])
