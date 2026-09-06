"""Authenticated manual Gmail connection and sync endpoints."""

import html
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import verify_jwt
from app.config import settings
from app.database import get_db
from app.models.gmail import GmailConnection, GmailMessage
from app.services.gmail_client import build_authorization_url, credential_values, exchange_code
from app.services.gmail_ingestion import sync_nabil_alerts
from app.services.gmail_security import create_oauth_state, validate_oauth_state

router = APIRouter()


def _user_id(payload: dict | None) -> str:
    if not payload and not settings.auth_enabled:
        return "local-development-user"
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return str(payload["sub"])


@router.get("/connect")
def connect_gmail(user: dict | None = Depends(verify_jwt)):
    try:
        return {"authorization_url": build_authorization_url(create_oauth_state(_user_id(user)))}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/oauth/callback", response_class=HTMLResponse, include_in_schema=False)
def gmail_oauth_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    connected = False
    try:
        user_id = validate_oauth_state(state)
        credentials = exchange_code(code)
        if not credentials.refresh_token:
            raise ValueError("Google did not return a refresh token; reconnect and approve offline access")
        from googleapiclient.discovery import build
        from app.config import settings
        profile = build("gmail", "v1", credentials=credentials, cache_discovery=False).users().getProfile(userId="me").execute()
        email = profile.get("emailAddress")
        if not email:
            raise ValueError("Could not determine connected Gmail address")
        values = credential_values(credentials)
        connection = db.query(GmailConnection).filter(GmailConnection.user_id == user_id).first()
        if connection is None:
            connection = GmailConnection(user_id=user_id, email=email, **values)
            db.add(connection)
        else:
            connection.email = email
            for key, value in values.items():
                setattr(connection, key, value)
        db.commit()
        message = "Gmail connected. You can close this window."
        connected = True
    except Exception as exc:
        db.rollback()
        message = f"Gmail connection failed: {exc}"
    safe_message = html.escape(message)
    safe_connected = "true" if connected else "false"
    return HTMLResponse(
        f"<html><body><p>{safe_message}</p><script>"
        f"window.opener?.postMessage({{type: 'fintrack-gmail-oauth', connected: {safe_connected}, message: {__import__('json').dumps(message)}}}, '*');"
        "window.close();</script></body></html>"
    )


@router.get("/status")
def gmail_status(user: dict | None = Depends(verify_jwt), db: Session = Depends(get_db)):
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == _user_id(user)).first()
    if not connection:
        return {"connected": False, "email": None, "last_successful_sync_at": None}
    return {"connected": True, "email": connection.email, "last_successful_sync_at": connection.last_successful_sync_at}


@router.post("/sync")
def gmail_sync(user: dict | None = Depends(verify_jwt), db: Session = Depends(get_db)):
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == _user_id(user)).first()
    if not connection:
        raise HTTPException(status_code=409, detail="Gmail is not connected")
    try:
        return sync_nabil_alerts(db, connection)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Gmail sync failed: {exc}")


@router.delete("/disconnect")
def gmail_disconnect(user: dict | None = Depends(verify_jwt), db: Session = Depends(get_db)):
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == _user_id(user)).first()
    if connection:
        db.query(GmailMessage).filter(GmailMessage.connection_id == connection.id).delete(synchronize_session=False)
        db.delete(connection)
        db.commit()
    return {"connected": False}
