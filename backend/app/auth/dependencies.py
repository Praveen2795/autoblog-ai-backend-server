"""
Authentication dependencies for FastAPI routes.
"""
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.jwt import verify_token


# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Dependency to get the current authenticated user.
    Raises 401 if not authenticated.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user": user}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Dependency to optionally get the current user.
    Returns None if not authenticated (doesn't raise exception).
    
    Usage:
        @router.get("/public")
        async def public_route(user: Optional[dict] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user['sub']}"}
            return {"message": "Hello anonymous"}
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    return verify_token(token)
