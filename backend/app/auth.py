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
