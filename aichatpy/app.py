"""
AI 상담 API (회원 전용).
- GET  /api/ai/chat/<cnsl_id>  : bot_msg 조회 (VisualChat 형식 반환)
- POST /api/ai/chat/<cnsl_id>  : 사용자 메시지 전송 → OpenAI 응답 저장 후 반환
- POST /api/ai/chat/<cnsl_id>/summary : 요약 생성 후 summary 저장
"""
import os
from datetime import datetime
from flask import Flask, jsonify, request

from config import CORS_ORIGINS
from db import append_message, get_bot_msg, update_summary, upsert_bot_msg
from openai_client import get_ai_reply

app = Flask(__name__)

# CORS
@app.after_request
def cors_headers(resp):
    origin = request.environ.get("HTTP_ORIGIN")
    if origin and (origin in CORS_ORIGINS or "*" in CORS_ORIGINS):
        resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-User-Email"
    return resp


def _require_member():
    """회원 전용: X-User-Email 필수."""
    email = (request.headers.get("X-User-Email") or "").strip()
    if not email:
        return None, 401, {"message": "회원만 이용 가능합니다."}
    return email, None, None


def _row_to_visual_format(row):
    """bot_msg 행을 VisualChat 응답 형식으로 변환."""
    if not row:
        return None
    msg_data = row.get("msg_data") or {"content": []}
    created = row.get("created_at")
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    return {
        "chatId": row.get("bot_msg_id"),
        "cnslId": row.get("cnsl_id"),
        "cnslerId": "",
        "memberId": row.get("member_id"),
        "role": "user",
        "createdAt": created,
        "summary": row.get("summary"),
        "msg_data": msg_data,
    }


@app.route("/api/ai/chat/<int:cnsl_id>", methods=["GET", "OPTIONS"])
def get_chat(cnsl_id):
    if request.method == "OPTIONS":
        return "", 204
    member_id, err, code = _require_member()
    if err:
        return jsonify({"error": "UNAUTHORIZED", "message": err}), code
    row = get_bot_msg(cnsl_id, member_id)
    # VisualChat 형식: 목록으로 반환 (1건)
    out = [_row_to_visual_format(row)] if row else []
    return jsonify(out)


@app.route("/api/ai/chat/<int:cnsl_id>", methods=["POST"])
def post_chat(cnsl_id):
    member_id, err, code = _require_member()
    if err:
        return jsonify({"error": "UNAUTHORIZED", "message": err}), code
    body = request.get_json() or {}
    content = (body.get("content") or body.get("text") or "").strip()
    if not content:
        return jsonify({"error": "BAD_REQUEST", "message": "content 필수"}), 400
    # 기존 대화 로드
    row = get_bot_msg(cnsl_id, member_id)
    content_list = (row.get("msg_data") or {}).get("content") if row else []
    if not isinstance(content_list, list):
        content_list = []
    history = [{"speaker": x.get("speaker"), "text": x.get("text")} for x in content_list]
    # 사용자 메시지 저장
    append_message(cnsl_id, member_id, "user", content)
    # AI 응답 생성 및 저장
    ai_text = get_ai_reply(content, history)
    row = append_message(cnsl_id, member_id, "ai", ai_text)
    return jsonify(_row_to_visual_format(row))


@app.route("/api/ai/chat/<int:cnsl_id>/summary", methods=["POST"])
def post_summary(cnsl_id):
    member_id, err, code = _require_member()
    if err:
        return jsonify({"error": "UNAUTHORIZED", "message": err}), code
    row = get_bot_msg(cnsl_id, member_id)
    if not row:
        return jsonify({"error": "NOT_FOUND", "message": "해당 상담 기록이 없습니다."}), 404
    content_list = (row.get("msg_data") or {}).get("content") or []
    if not isinstance(content_list, list):
        content_list = []
    texts = [f"{x.get('speaker','')}: {x.get('text','')}" for x in content_list]
    full_text = "\n".join(texts)
    if not full_text.strip():
        return jsonify({"error": "BAD_REQUEST", "message": "요약할 대화가 없습니다."}), 400
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        r = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "다음 상담 대화를 3~5문장으로 요약해 주세요."},
                {"role": "user", "content": full_text},
            ],
            max_tokens=300,
        )
        summary = (r.choices[0].message.content or "").strip()
    except Exception as e:
        return jsonify({"error": "SUMMARY_FAILED", "message": str(e)}), 500
    row = update_summary(cnsl_id, member_id, summary)
    return jsonify(_row_to_visual_format(row))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
