from sqlalchemy import text
from app.db import engine
import random
from .common import LiveDiffculty


def create_room(live_id: int, select_difficully: LiveDiffculty) -> int:
    room_id = random.randint(0, 1000000)
    with engine.begin() as conn:
        result = conn.execute(
            text("INSERT INTO `room` (room_id, live_id, joined_user_count,max_user_count) VALUES(:room_id, :live_id,:joined_user_count,:max_user_count)"),
            {"room_id": room_id, "live_id": live_id ,"joined_user_count": 0,"max_user_count":4},
        )
    return room_id
