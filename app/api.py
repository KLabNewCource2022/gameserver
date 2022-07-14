from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomInfo,
    RoomUser,
    SafeUser,
    WaitRoomStatus,
)

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
    live_id: int  # ルームで遊ぶ楽曲のID
    select_difficulty: LiveDifficulty  # 選択難易度


class RoomCreateResponse(BaseModel):
    room_id: int  # 発行されたルームのID（以後の通信はこのiDを添える）


@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    """ルームを新規で建てる。"""
    room_id: int = model.create_room(req.live_id, req.select_difficulty)
    model.join_room(room_id, req.select_difficulty, token)
    return RoomCreateResponse(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    """入場可能なルーム一覧を取得"""
    room_info_list: list[RoomInfo] = model.find_enable_room(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


class RoomJoinRequest(BaseModel):
    room_id: int  # 入るルーム
    select_difficulty: LiveDifficulty  # 選択難易度


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult  # ルーム入場結果


@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    """上記listのルームに入場。"""
    result: JoinRoomResult = model.join_room(req.room_id, req.select_difficulty, token)
    return RoomJoinResponse(join_room_result=result)


class RoomWaitRequest(BaseModel):
    room_id: int  # 対象ルーム


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus  # 結果
    room_user_list: list[RoomUser]  # ルームにいるプレイヤー一覧


@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    """ルーム待機中（ポーリング）。APIの結果でゲーム開始がわかる。 クライアントはn秒間隔で投げる想定。"""
    status: WaitRoomStatus = model.room_status(req.room_id)
    room_user_list: list[RoomUser] = model.room_member(req.room_id, token)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


class RoomStartRequest(BaseModel):
    room_id: int  # 対象ルーム


@app.post("/room/start", response_model=Empty)
def room_start(req: RoomStartRequest):
    """ルームのライブ開始。部屋のオーナーがたたく。"""
    model.room_start_live(req.room_id)
    return {}


class RoomEndRequest(BaseModel):
    room_id: int  # 対象ルーム
    judge_count_list: list[int]  # 各判定数
    score: int  # スコア


@app.post("/room/end", response_model=Empty)
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    """ルームのライブ終了時リクエスト。ゲーム終わったら各人が叩く。"""
    model.set_room_user_result(req.room_id, req.judge_count_list, req.score, token)
    return {}


class RoomResultRequest(BaseModel):
    room_id: int  # 対象ルーム


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]  # 自身を含む各ユーザーの結果。※全員揃っていない待機中は[]が返却される想定


@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest):
    """ルーム待機中（ポーリング）。APIの結果でゲーム開始がわかる。 クライアントはn秒間隔で投げる想定。"""
    return RoomResultResponse(result_user_list=[])


class RoomLeaveRequest(BaseModel):
    room_id: int  # 対象ルーム


@app.post("/room/leave", response_model=Empty)
def room_leave(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    """ルーム退出リクエスト。オーナーも /room/join で参加した参加者も実行できる。"""
    model.leave_room(req.room_id, token)
    return {}
