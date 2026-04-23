from typing import List
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel

http_bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    username: str
    roles: List[str]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = credentials.credentials

    try:
        # Simplified: parse claims without verifying signature.
        # Keycloak puts roles in realm_access.roles and username in preferred_username.
        claims = jwt.get_unverified_claims(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Basic exp check
    exp = claims.get("exp")
    if exp is not None:
        now_ts = datetime.now(timezone.utc).timestamp()
        if now_ts > exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )

    username = claims.get("preferred_username") or claims.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: no username",
        )

    roles = claims.get("realm_access", {}).get("roles", [])
    return CurrentUser(username=username, roles=roles)


def require_roles(allowed_roles: List[str]):
    """
    Dependency generator: require at least one of the given roles.
    Usage: current_user = Depends(require_roles(["admin", "support"]))
    """
    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(r in current_user.roles for r in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return _dependency
