
import os
import time
import hmac
import hashlib
import secrets
import json
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import PlainTextResponse

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
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")


LOGIN_URL = "https://www.facebook.com/dialog/oauth"

# Temporary in-memory storage for this prototype.
# A restart or redeployment clears this data.
connected_accounts = {}
used_states = set()


def create_state():
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
            detail="Invalid, expired, or already-used OAuth state."
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
            raise ValueError("Access token missing from Meta response.")

        # Never return the access token to the browser.
        connected_accounts["default"] = {
            "access_token": access_token,
            "connected_at": int(time.time())
        }

        return {
            "connected": True,
            "message": "Instagram authorization successful."
        }

    except Exception as exc:
        print(f"Instagram OAuth error: {type(exc).__name__}", flush=True)

        raise HTTPException(
            status_code=502,
            detail="Unable to complete Instagram authorization."
        )


@router.get("/webhook")
async def verify_instagram_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(
        default=None, alias="hub.verify_token"
    ),
    challenge: str | None = Query(
        default=None, alias="hub.challenge"
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


@router.post("/webhook")
async def receive_instagram_webhook(request: Request):
    if not META_APP_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Meta App Secret is not configured."
        )

    raw_body = await request.body()

    signature = request.headers.get("X-Hub-Signature-256", "")

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

    # Temporary: log event structure, not access tokens or secrets.
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            print(
                "Instagram webhook field:",
                change.get("field"),
                flush=True
            )

    return {"status": "received"}

