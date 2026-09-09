"""Authoritative Firestore session revision repository.

Implements:
- Monotonic revision incrementing
- Optimistic concurrency control via expected_revision
- operation_id deduplication
- Immutability of protected tracks
- Clear UNAVAILABLE signaling if Firebase credentials are unset
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.config import settings
from app.models import Session, CueEdit, CueEditAction, EditBatch, ToolResult, ToolResultStatus

logger = logging.getLogger(__name__)

# Cached Firestore client instance
_db_client = None


def get_firestore_client():
    """Retrieve or initialize Firestore client if credentials are configured."""
    global _db_client
    if _db_client is not None:
        return _db_client

    if not settings.is_firestore_configured:
        return None

    try:
        from google.cloud import firestore
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            _db_client = firestore.Client.from_service_account_json(
                settings.GOOGLE_APPLICATION_CREDENTIALS
            )
        elif settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY:
            from google.oauth2 import service_account
            private_key = settings.formatted_firebase_private_key
            credentials = service_account.Credentials.from_service_account_info({
                "project_id": settings.FIREBASE_PROJECT_ID,
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "private_key": private_key,
                "token_uri": "https://oauth2.googleapis.com/token",
            })
            _db_client = firestore.Client(project=settings.FIREBASE_PROJECT_ID, credentials=credentials)
        elif settings.FIREBASE_PROJECT_ID:
            _db_client = firestore.Client(project=settings.FIREBASE_PROJECT_ID)
        return _db_client
    except Exception as e:
        logger.error(f"Failed to initialize Firestore client: {e}")
        return None


class FirestoreRevisionStore:
    """Manages sessions, revisions, and operations in Firestore."""

    def __init__(self):
        self.collection_name = "sound_rehearsal_sessions"
        self.operations_collection = "sound_rehearsal_operations"

    @property
    def is_available(self) -> bool:
        return get_firestore_client() is not None

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Fetch current session state."""
        db = get_firestore_client()
        if db is None:
            raise RuntimeError("Firestore is UNAVAILABLE: Firebase credentials not configured.")

        doc_ref = db.collection(self.collection_name).document(session_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return Session(**data)

    async def create_session(self, session: Session) -> Session:
        """Create a new session record in Firestore."""
        db = get_firestore_client()
        if db is None:
            raise RuntimeError("Firestore is UNAVAILABLE: Firebase credentials not configured.")

        doc_ref = db.collection(self.collection_name).document(session.id)
        if doc_ref.get().exists:
            raise ValueError(f"Session {session.id} already exists")

        data = session.model_dump(mode="json")
        doc_ref.set(data)
        return session

    async def apply_edit_batch(self, batch: EditBatch, owner_uid: str) -> ToolResult:
        """Atomically apply an edit batch enforcing optimistic locking, idempotency, and track protections."""
        db = get_firestore_client()
        if db is None:
            return ToolResult(
                operation_id=batch.operation_id,
                status=ToolResultStatus.UNAVAILABLE,
                revision=-1,
                error_code="FIRESTORE_UNAVAILABLE",
                data={"error": "Firestore is not configured. Session edits cannot be committed."},
            )

        # 1. Check idempotency: did we already process this operation_id?
        op_ref = db.collection(self.operations_collection).document(batch.operation_id)
        existing_op = op_ref.get()
        if existing_op.exists:
            op_data = existing_op.to_dict()
            return ToolResult(**op_data["result"])

        session_ref = db.collection(self.collection_name).document(batch.session_id)

        # Execute inside a transaction
        from google.cloud import firestore

        transaction = db.transaction()

        @firestore.transactional
        def _apply_in_tx(tx, s_ref, o_ref):
            s_snap = s_ref.get(transaction=tx)
            if not s_snap.exists:
                raise ValueError(f"Session {batch.session_id} not found")

            session_data = s_snap.to_dict()
            current_session = Session(**session_data)

            if current_session.owner_uid != owner_uid:
                raise PermissionError("Ownership check failed")

            if current_session.revision != batch.expected_revision:
                raise ValueError(
                    f"STALE_REVISION: expected {batch.expected_revision}, but current revision is {current_session.revision}"
                )

            # Map existing cues by id
            cues_map = {c.id: c for c in current_session.cues}
            protected_tracks = set(current_session.protected_track_ids)

            for edit in batch.edits:
                existing_cue = cues_map.get(edit.cue_id)

                # Track protection check
                if existing_cue and existing_cue.track_id in protected_tracks:
                    raise ValueError(
                        f"PROTECTED_TRACK: cannot modify cue {edit.cue_id} on protected track '{existing_cue.track_id}'"
                    )

                if edit.action == CueEditAction.ADD:
                    if not edit.cue:
                        raise ValueError(f"Cue data missing for ADD action on {edit.cue_id}")
                    if edit.cue.track_id in protected_tracks:
                        raise ValueError(
                            f"PROTECTED_TRACK: cannot add cue {edit.cue_id} to protected track '{edit.cue.track_id}'"
                        )
                    if edit.cue_id in cues_map:
                        raise ValueError(f"Cue {edit.cue_id} already exists")
                    cues_map[edit.cue_id] = edit.cue

                elif edit.action == CueEditAction.MODIFY:
                    if not edit.cue:
                        raise ValueError(f"Cue data missing for MODIFY action on {edit.cue_id}")
                    if edit.cue_id not in cues_map:
                        raise ValueError(f"Cue {edit.cue_id} not found for modification")
                    if edit.cue.track_id in protected_tracks:
                        raise ValueError(
                            f"PROTECTED_TRACK: cannot move cue into protected track '{edit.cue.track_id}'"
                        )
                    cues_map[edit.cue_id] = edit.cue

                elif edit.action == CueEditAction.REMOVE:
                    if edit.cue_id in cues_map:
                        del cues_map[edit.cue_id]

            # Update session
            new_revision = current_session.revision + 1
            current_session.cues = list(cues_map.values())
            current_session.revision = new_revision
            current_session.updated_at = datetime.now(timezone.utc)

            # Validate overall scene duration bounds
            for c in current_session.cues:
                if c.timeline_end_ms > current_session.scene_duration_ms:
                    raise ValueError(
                        f"Cue {c.id} ends at {c.timeline_end_ms}ms which exceeds scene duration {current_session.scene_duration_ms}ms"
                    )

            # Persist session update
            tx.set(s_ref, current_session.model_dump(mode="json"))

            # Record operation for idempotency
            result = ToolResult(
                operation_id=batch.operation_id,
                status=ToolResultStatus.SUCCESS,
                revision=new_revision,
                data={
                    "session_id": current_session.id,
                    "applied_revision": new_revision,
                    "cues_count": len(current_session.cues),
                    "rationale": batch.rationale_summary,
                },
            )
            tx.set(o_ref, {
                "operation_id": batch.operation_id,
                "session_id": batch.session_id,
                "owner_uid": owner_uid,
                "result": result.model_dump(mode="json"),
                "applied_at": datetime.now(timezone.utc).isoformat(),
            })

            return result

        try:
            return _apply_in_tx(transaction, session_ref, op_ref)
        except ValueError as ve:
            err_msg = str(ve)
            err_code = "STALE_REVISION" if "STALE_REVISION" in err_msg else "VALIDATION_ERROR"
            return ToolResult(
                operation_id=batch.operation_id,
                status=ToolResultStatus.ERROR,
                revision=batch.expected_revision,
                error_code=err_code,
                retryable=(err_code == "STALE_REVISION"),
                data={"error": err_msg},
            )
        except Exception as ex:
            return ToolResult(
                operation_id=batch.operation_id,
                status=ToolResultStatus.ERROR,
                revision=batch.expected_revision,
                error_code="TRANSACTION_FAILED",
                retryable=True,
                data={"error": str(ex)},
            )


# Global singleton instance
firestore_store = FirestoreRevisionStore()
