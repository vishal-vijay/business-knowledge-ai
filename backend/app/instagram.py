
import os
import time
import hmac
import hashlib
import secrets
import json
import urllib.parse
import urllib.request
import urllib.error
import threading

from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, PlainTextResponse

from app.services.answer_service import answer_question


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

router = APIRouter()

META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
INSTAGRAM_CONFIG_ID = os.getenv("INSTAGRAM_CONFIG_ID")
INSTAGRAM_REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI")

INSTAGRAM_WEBHOOK_VERIFY_TOKEN = os.getenv(
    "INSTAGRAM_WEBHOOK_VERIFY_TOKEN"
)

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
INSTAGRAM_BUSINESS_ID = os.getenv("INSTAGRAM_BUSINESS_ID")

GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")

LOGIN_URL = "https://www.facebook.com/dialog/oauth"

# Prototype-only in-memory storage.
connected_accounts = {}
used_states = set()
processed_comments = set()
processing_comments = set()

comment_lock = threading.Lock()


# -----------------------------------------
# OAUTH LOGIN
# -----------------------------------------

def create_state():
    if not META_APP_SECRET:
        raise RuntimeError("Meta App Secret is missing")

    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)

    message = f"{timestamp}.{nonce}"

    signature = hmac.new(
        META_APP_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"{message}.{signature}"


def validate_state(state: str):
    try:
        timestamp, nonce, signature = state.split(".", 2)

        message = f"{timestamp}.{nonce}"

        expected = hmac.new(
            META_APP_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return False

        if time.time() - int(timestamp) > 600:
            return False

        if nonce in used_states:
            return False

        used_states.add(nonce)
        return True

    except (ValueError, TypeError):
        return False


@router.get("/login")
def instagram_login():

    if not all([
        META_APP_ID,
        META_APP_SECRET,
        INSTAGRAM_CONFIG_ID,
        INSTAGRAM_REDIRECT_URI
    ]):
        raise HTTPException(
            status_code=500,
            detail="Instagram OAuth configuration is incomplete."
        )

    state = create_state()

    params = {
        "client_id": META_APP_ID,
        "config_id": INSTAGRAM_CONFIG_ID,
        "display": "popup",
        "override_default_response_type": "true",
        "redirect_uri": INSTAGRAM_REDIRECT_URI,
        "response_type": "code",
        "state": state,
        "prompt": "login"
    }

    authorization_url = (
        f"{LOGIN_URL}?{urllib.parse.urlencode(params)}"
    )

    return RedirectResponse(authorization_url)


@router.get("/callback")
def instagram_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None)
):

    if error:
        raise HTTPException(
            status_code=400,
            detail="Instagram authorization was cancelled or denied."
        )

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Authorization code or state is missing."
        )

    if not validate_state(state):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state."
        )

    params = {
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "redirect_uri": INSTAGRAM_REDIRECT_URI,
        "code": code
    }

    token_url = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token?"
        f"{urllib.parse.urlencode(params)}"
    )

    try:
        request = urllib.request.Request(token_url)

        with urllib.request.urlopen(request, timeout=20) as response:
            token_data = json.loads(response.read().decode())

        access_token = token_data.get("access_token")

        if not access_token:
            raise ValueError("Access token missing")

        connected_accounts["default"] = {
            "access_token": access_token,
            "connected_at": int(time.time())
        }

        return {
            "connected": True,
            "message": "Instagram authorization successful."
        }

    except Exception as exc:
        print(
            f"Instagram OAuth error: {type(exc).__name__}",
            flush=True
        )

        raise HTTPException(
            status_code=502,
            detail="Unable to complete Instagram authorization."
        )


# -----------------------------------------
# WEBHOOK VERIFICATION
# -----------------------------------------

@router.get("/webhook")
async def verify_instagram_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(
        default=None,
        alias="hub.verify_token"
    ),
    challenge: str | None = Query(
        default=None,
        alias="hub.challenge"
    )
):

    if not INSTAGRAM_WEBHOOK_VERIFY_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="Webhook verify token is not configured."
        )

    if (
        mode == "subscribe"
        and verify_token
        and hmac.compare_digest(
            verify_token,
            INSTAGRAM_WEBHOOK_VERIFY_TOKEN
        )
        and challenge
    ):
        return PlainTextResponse(challenge)

    raise HTTPException(
        status_code=403,
        detail="Webhook verification failed."
    )


# -----------------------------------------
# SEND INSTAGRAM COMMENT REPLY
# -----------------------------------------

def send_instagram_reply(comment_id: str, message: str):

    if not all([
        INSTAGRAM_ACCESS_TOKEN,
        INSTAGRAM_ACCOUNT_ID
    ]):
        raise RuntimeError("Instagram API configuration is incomplete")

    url = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/"
        f"{urllib.parse.quote(comment_id, safe='')}/replies"
    )

    data = urllib.parse.urlencode({
        "message": message,
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }).encode()

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode())

        print(
            "Instagram reply sent:",
            {"comment_id": comment_id, "success": True},
            flush=True
        )

        return result

    except urllib.error.HTTPError as exc:
        # Do not log the request URL, token or customer content.
        print(
            "Instagram reply API error:",
            {"status": exc.code},
            flush=True
        )
        raise


# -----------------------------------------
# PROCESS COMMENT
# -----------------------------------------

def process_comment(
    comment_id: str,
    comment_text: str,
    commenter_id: str,
    account_id: str
):

    if not INSTAGRAM_BUSINESS_ID:
        print("Instagram business ID missing", flush=True)
        return

    if not comment_text.strip():
        return

    if not INSTAGRAM_ACCESS_TOKEN:
        print("Instagram access token missing", flush=True)
        return

    try:
        result = answer_question(
            question=comment_text,
            business_id=INSTAGRAM_BUSINESS_ID
        )

        answer = result.get("answer", "").strip()

        if not answer:
            print(
                "No answer generated for comment:",
                comment_id,
                flush=True
            )
            return

        # Avoid replying with an answer when no relevant source was found.
        if not result.get("sources"):
            print(
                "No relevant business source found:",
                comment_id,
                flush=True
            )
            return

        # Keep public comment replies concise.
        if len(answer) > 900:
            answer = answer[:897].rsplit(" ", 1)[0] + "..."

        send_instagram_reply(
            comment_id=comment_id,
            message=answer
        )

        with comment_lock:
            processed_comments.add(comment_id)

    except Exception as exc:
        print(
            "Comment processing failed:",
            {
                "comment_id": comment_id,
                "error_type": type(exc).__name__
            },
            flush=True
        )

    finally:
        with comment_lock:
            processing_comments.discard(comment_id)


# -----------------------------------------
# PROCESS WEBHOOK PAYLOAD
# -----------------------------------------

def process_webhook_payload(payload: dict):

    if payload.get("object") != "instagram":
        return

    for entry in payload.get("entry", []):

        account_id = str(entry.get("id", ""))

        # Only process the Instagram account configured for this demo.
        if account_id != str(INSTAGRAM_ACCOUNT_ID):
            continue

        for change in entry.get("changes", []):

            if change.get("field") != "comments":
                continue

            value = change.get("value", {})

            comment_id = str(value.get("id", ""))
            comment_text = value.get("text", "")

            commenter = value.get("from", {})
            commenter_id = str(commenter.get("id", ""))

            # Ignore events without the required information.
            if not comment_id or not comment_text:
                continue

            # Ignore comments made by our own Instagram account.
            if commenter_id == account_id:
                continue

            if str(value.get("self_ig_scoped_id", "")) == account_id:
                continue

            # Ignore replies to existing comments for this first version.
            if value.get("parent_id"):
                continue

            with comment_lock:
                if (
                    comment_id in processed_comments
                    or comment_id in processing_comments
                ):
                    continue

                processing_comments.add(comment_id)

            process_comment(
                comment_id=comment_id,
                comment_text=comment_text,
                commenter_id=commenter_id,
                account_id=account_id
            )


# -----------------------------------------
# RECEIVE WEBHOOK EVENTS
# -----------------------------------------

@router.post("/webhook")
async def receive_instagram_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):

    if not META_APP_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Meta App Secret is not configured."
        )

    raw_body = await request.body()

    signature = request.headers.get(
        "X-Hub-Signature-256",
        ""
    )

    expected_signature = "sha256=" + hmac.new(
        META_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(
            status_code=403,
            detail="Invalid webhook signature."
        )

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload."
        )

    event_count = 0

    for entry in payload.get("entry", []):
        event_count += len(entry.get("changes", []))

    print(
        "Instagram webhook received:",
        {
            "object": payload.get("object"),
            "entry_count": len(payload.get("entry", [])),
            "event_count": event_count
        },
        flush=True
    )

    background_tasks.add_task(
        process_webhook_payload,
        payload
    )

    return {"status": "received"}
