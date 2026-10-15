"""Authorization utilities and dependency guards for Cineverse.

In this educational project, authenticating users via client-supplied demo user IDs
(passed via X-User-Id HTTP header or user_id query parameter) illustrates role-based
access control (RBAC) and resource ownership verification without introducing full JWT/OAuth flows.
"""

from typing import Optional
from fastapi import Header, Query, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.errors import ForbiddenError, NotFoundError
from app.models import User, UserRole


def get_current_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    caller_user_id: Optional[int] = Query(None, alias="user_id"),
) -> Optional[int]:
    """Extract active user_id from HTTP header or query parameter."""
    if x_user_id is not None and x_user_id.strip():
        try:
            return int(x_user_id.strip())
        except ValueError:
            return None
    return caller_user_id


def require_admin(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    caller_user_id: Optional[int] = Query(None, alias="user_id"),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Verify administrator privileges.

    If an explicit user is supplied (via X-User-Id header or user_id query parameter),
    the user must exist in the database and have the 'admin' role. If non-admin is supplied,
    raises 403 Forbidden.
    """
    uid = None
    if x_user_id is not None and x_user_id.strip():
        try:
            uid = int(x_user_id.strip())
        except ValueError:
            raise ForbiddenError("Invalid X-User-Id header format. Expected integer user ID.")
    elif caller_user_id is not None:
        uid = caller_user_id

    if uid is None:
        # If no user ID header/query is provided, require admin
        raise ForbiddenError("Administrator access required: missing X-User-Id header or user_id")

    user = db.get(User, uid)
    if not user:
        raise NotFoundError(f"User with ID {uid} was not found")

    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Administrator privileges required for this action")

    return user
