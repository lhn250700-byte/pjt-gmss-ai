"""
bot_msg 테이블 접근.
스키마: bot_msg_id(PK), cnsl_id, member_id, msg_data(jsonb), summary(text), created_at, updated_at
cnsl_id당 1행, msg_data = { "content": [ { "speaker": "user"|"ai", "text": "...", "type": "chat", "timestamp": 123 } ] }
"""
import json
import os
import time
from contextlib import contextmanager
from typing import Any, Optional

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_bot_msg(cnsl_id: int, member_id: str) -> Optional[dict]:
    """cnsl_id + member_id에 해당하는 bot_msg 1건 조회. 없으면 None."""
    if not DATABASE_URL:
        return None
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT bot_msg_id, cnsl_id, member_id, msg_data, summary, created_at, updated_at
                FROM bot_msg
                WHERE cnsl_id = %s AND member_id = %s
                LIMIT 1
                """,
                (cnsl_id, member_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)


def upsert_bot_msg(
    cnsl_id: int,
    member_id: str,
    msg_data: dict,
    summary: Optional[str] = None,
) -> dict:
    """
    bot_msg 1건 삽입 또는 갱신.
    msg_data = { "content": [ { speaker, text, type, timestamp }, ... ] }
    """
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    content_list = (msg_data or {}).get("content") or []
    msg_data_json = json.dumps({"content": content_list}, ensure_ascii=False)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO bot_msg (cnsl_id, member_id, msg_data, summary, created_at, updated_at)
                VALUES (%s, %s, %s::jsonb, %s, %s::timestamp, %s::timestamp)
                ON CONFLICT (cnsl_id, member_id)
                DO UPDATE SET
                    msg_data = EXCLUDED.msg_data,
                    summary = COALESCE(EXCLUDED.summary, bot_msg.summary),
                    updated_at = EXCLUDED.updated_at
                RETURNING bot_msg_id, cnsl_id, member_id, msg_data, summary, created_at, updated_at
                """,
                (cnsl_id, member_id, msg_data_json, summary or None, now, now),
            )
            row = cur.fetchone()
    if not row:
        raise RuntimeError("upsert_bot_msg failed")
    return dict(row)


def append_message(cnsl_id: int, member_id: str, speaker: str, text: str) -> dict:
    """msg_data.content에 한 건 추가 후 저장. speaker: 'user' | 'ai'."""
    existing = get_bot_msg(cnsl_id, member_id)
    content = list((existing or {}).get("msg_data") or {}).get("content") or []
    if isinstance(content, str):
        content = []
    content.append({
        "speaker": speaker,
        "text": text,
        "type": "chat",
        "timestamp": int(time.time() * 1000),
    })
    return upsert_bot_msg(cnsl_id, member_id, {"content": content})


def update_summary(cnsl_id: int, member_id: str, summary: str) -> dict:
    """summary만 갱신."""
    existing = get_bot_msg(cnsl_id, member_id)
    if not existing:
        return upsert_bot_msg(cnsl_id, member_id, {"content": []}, summary=summary)
    msg_data = existing.get("msg_data") or {"content": []}
    return upsert_bot_msg(cnsl_id, member_id, msg_data, summary=summary)
