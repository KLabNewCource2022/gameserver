from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import SafeUser

app = FastAPI()

# Sample APIs


@app.get("/")
async def root():
    return {"message": "Hello World"}


# Enum
class LiveDifficulty(Enum):
    normal  = 0
    hard    = 1


class JoinRoomResult(Enum):
    Ok          = 1  # 入場OK
    RoomFull    = 2  # 満員
    Disbanded   = 3  # 解散済み
    OtherError  = 4  # その他エラー


class WaitRoomStatus(Enum):
    Waiting     = 1  # ホストがライブ開始ボタン押すのを待っている
    LiveStart	= 2  # ライブ画面遷移OK
    Dissolution	= 3  # 解散された
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
def RoomCreate(req: RoomCreateResquest ,token: str = Depends(get_auth_token)):
    room_id = model.create_room(token, live_id=req.live_id, select_difficulty=req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)
