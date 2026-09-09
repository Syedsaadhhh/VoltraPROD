"""Authentication and ownership verification.

Supports Firebase Auth tokens when configured, with safe local/dev fallback
for test harnesses and anonymous judge evaluation.
"""

import logging
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# Optional firebase_admin initialization
_firebase_initialized = False


def _init_firebase_if_possible() -> bool:
    global _firebase_initialized
    if _firebase_initialized:
        return True

    if not settings.is_firestore_configured:
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            if settings.GOOGLE_APPLICATION_CREDENTIALS:
                cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
                firebase_admin.initialize_app(cred)
            elif settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY:
                private_key = settings.formatted_firebase_private_key
                cred = credentials.Certificate({
                    "type": "service_account",
                    "project_id": settings.FIREBASE_PROJECT_ID,
                    "client_email": settings.FIREBASE_CLIENT_EMAIL,
                    "private_key": private_key,
                    "token_uri": "https://oauth2.googleapis.com/token",
                })
                firebase_admin.initialize_app(cred)
            elif settings.FIREBASE_PROJECT_ID:
                firebase_admin.initialize_app(options={"projectId": settings.FIREBASE_PROJECT_ID})
        _firebase_initialized = True
        return True
    except Exception as e:
        logger.warning(f"Could not initialize Firebase Admin SDK: {e}")
        return False


def verify_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """Extract and strictly verify user ID from Firebase ID token.
    
    All users (including anonymous users created via Firebase Anonymous Auth)
    must present a genuine cryptographically verified Firebase ID token.
    No caller-supplied user IDs or arbitrary string bypasses are permitted.
    """
    if not auth_header or not auth_header.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header: Bearer <firebase_id_token> required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.credentials.strip()

    if not _init_firebase_if_possible():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable: Firebase Admin SDK is not configured",
        )

    try:
        from firebase_admin import auth
        decoded = auth.verify_id_token(token, check_revoked=True)
        uid = decoded.get("uid")
        if not uid:
            raise ValueError("Token does not contain a valid uid")
        return uid
    except Exception as e:
        logger.warning(f"Firebase token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def assert_session_ownership(session_owner_uid: str, current_user_uid: str) -> None:
    """Enforce that current caller is the authoritative owner of the session."""
    if session_owner_uid != current_user_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: caller does not own this rehearsal session",
        )


_cached_public_config = None


async def get_public_firebase_config() -> dict:
    """Safely retrieve and cache public Firebase Web Client configuration. Never exposes service account secrets."""
    global _cached_public_config
    if _cached_public_config:
        return _cached_public_config

    # Explicit environment variable priority
    if settings.FIREBASE_WEB_API_KEY:
        _cached_public_config = {
            "apiKey": settings.FIREBASE_WEB_API_KEY,
            "authDomain": f"{settings.FIREBASE_PROJECT_ID}.firebaseapp.com" if settings.FIREBASE_PROJECT_ID else "",
            "projectId": settings.FIREBASE_PROJECT_ID or "",
            "appId": settings.FIREBASE_APP_ID or "1:773118731903:web:6c58b4804f0baf7c82c14a",
        }
        return _cached_public_config

    # Auto-resolve from Firebase Management API using service account credentials
    if settings.is_firestore_configured:
        try:
            import json
            import urllib.request
            import google.oauth2.service_account
            from google.auth.transport.requests import Request

            private_key = settings.formatted_firebase_private_key
            creds = google.oauth2.service_account.Credentials.from_service_account_info({
                "type": "service_account",
                "project_id": settings.FIREBASE_PROJECT_ID,
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "private_key": private_key,
                "token_uri": "https://oauth2.googleapis.com/token",
            }, scopes=["https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/firebase"])
            creds.refresh(Request())

            req = urllib.request.Request(
                f"https://firebase.googleapis.com/v1beta1/projects/{settings.FIREBASE_PROJECT_ID}/webApps",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            resp = urllib.request.urlopen(req, timeout=10)
            apps = json.loads(resp.read()).get("apps", [])
            if apps:
                app_id = apps[0]["appId"]
                req2 = urllib.request.Request(
                    f"https://firebase.googleapis.com/v1beta1/projects/{settings.FIREBASE_PROJECT_ID}/webApps/{app_id}/config",
                    headers={"Authorization": f"Bearer {creds.token}"},
                )
                cfg = json.loads(urllib.request.urlopen(req2, timeout=10).read())
                _cached_public_config = {
                    "apiKey": cfg.get("apiKey", ""),
                    "authDomain": cfg.get("authDomain", f"{settings.FIREBASE_PROJECT_ID}.firebaseapp.com"),
                    "projectId": cfg.get("projectId", settings.FIREBASE_PROJECT_ID),
                    "appId": cfg.get("appId", app_id),
                }
                logger.info(f"Auto-resolved public Firebase Web App configuration for '{settings.FIREBASE_PROJECT_ID}'")
                return _cached_public_config
        except Exception as ex:
            logger.warning(f"Could not auto-fetch public Firebase web app config: {ex}")

    # Fallback to minimal public descriptors
    _cached_public_config = {
        "apiKey": settings.FIREBASE_WEB_API_KEY or "",
        "authDomain": f"{settings.FIREBASE_PROJECT_ID}.firebaseapp.com" if settings.FIREBASE_PROJECT_ID else "",
        "projectId": settings.FIREBASE_PROJECT_ID or "",
        "appId": settings.FIREBASE_APP_ID or "1:773118731903:web:6c58b4804f0baf7c82c14a",
    }
    return _cached_public_config
