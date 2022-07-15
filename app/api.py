from calendar import leapdays
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from pyparsing import empty

from . import model
from .model import SafeUser

import room.common
from room.model import create_room, end_room, join_room, leave_room, list_room, result_room, start_room, wait_room

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
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# Room APIs

@app.post("/room/create", response_model=room.common.RoomCreateResponse)
def room_create(req: room.common.RoomCreateRequest,token:str = Depends(get_auth_token)):
    rid = create_room(req.live_id, req.select_difficulty, user_me(token))
    return rid


@app.post("/room/list", response_model=room.common.RoomListResponse)
def room_list(req: room.common.RoomListRequest):
    room_infos = list_room(req.live_id)
    return room_infos


@app.post("/room/join", response_model=room.common.RoomJoinResponse)
def room_join(req: room.common.RoomJoinRequest,token:str = Depends(get_auth_token)):
    result = join_room(req.room_id,req.select_difficulty,user_me(token))
    return result


@app.post("/room/wait", response_model=room.common.RoomWaitResponse)
def room_wait(req: room.common.RoomWaitRequest):
    room_info = wait_room(req.room_id)
    return room_info


@app.post("/room/start", response_model=Empty)
def room_start(req: room.common.RoomStartRequest):
    start_room(req.room_id)
    return {}


@app.post("/room/end", response_model=Empty)
def room_end(req: room.common.RoomEndRequest, token:str = Depends(get_auth_token)):
    end_room(req.room_id,req.judge_count_list,req.score,user_me(token))
    return {}


@app.post("/room/result", response_model=room.common.RoomResultResponse)
def room_result(req: room.common.RoomResultRequest, token:str = Depends(get_auth_token)):
    result = result_room(req.room_id,user_me(token))
    return result


@app.post("/room/leave", response_model=Empty)
def room_leave(req: room.common.RoomLeaveRequest, token:str = Depends(get_auth_token)):
    leave_room(req.room_id, user_me(token))
    return {}