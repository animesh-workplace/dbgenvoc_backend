import json
import string
import secrets
import ipaddress
from app.models import ApiToken
from typing import List, Optional
from sqlalchemy.orm import Session
from app.core import GERMLINE_TABLE_REGISTRY
from app.session import get_db, SessionLocal
from datetime import datetime, timedelta, timezone
from app.schema import TokenCreateRequest, TokenResponse
from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Security scheme for token authentication
security = HTTPBearer(auto_error=False)


class TokenInfo:
    def __init__(self, token: str, user_identifier: str, permissions: List[str] = None):
        self.token = token
        self.user_identifier = user_identifier
        self.permissions = permissions or []


async def verify_germline_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db),
) -> Optional[TokenInfo]:
    """
    Verify token for germline data access.
    Returns TokenInfo if valid, None if no token provided (for non-germline tables).
    Raises HTTPException for invalid tokens.
    """
    if not credentials:
        return None

    token = credentials.credentials
    client_ip = request.client.host

    # Query token from database
    db_token = (
        db.query(ApiToken).filter(ApiToken.token == token, ApiToken.is_active).first()
    )

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Check expiration
    if db_token.expires_at and datetime.utcnow() > db_token.expires_at:
        raise HTTPException(status_code=401, detail="Token has expired")

    # Check IP whitelist if configured
    if db_token.ip_whitelist:
        try:
            allowed_ips = json.loads(db_token.ip_whitelist)
            if not is_ip_allowed(client_ip, allowed_ips):
                raise HTTPException(
                    status_code=403, detail="Access denied from this IP address"
                )
        except json.JSONDecodeError:
            pass  # Skip IP check if JSON is invalid

    # Update last used timestamp
    db_token.last_used_at = datetime.utcnow()
    db.commit()

    # Parse permissions
    permissions = []
    if db_token.permissions:
        try:
            permissions = json.loads(db_token.permissions)
        except json.JSONDecodeError:
            pass

    return TokenInfo(
        token=token, user_identifier=db_token.user_identifier, permissions=permissions
    )


def is_ip_allowed(client_ip: str, allowed_ips: List[str]) -> bool:
    """Check if client IP is in the whitelist"""
    try:
        client_addr = ipaddress.ip_address(client_ip)
        for allowed_ip in allowed_ips:
            if "/" in allowed_ip:  # CIDR notation
                if client_addr in ipaddress.ip_network(allowed_ip):
                    return True
            else:  # Single IP
                if str(client_addr) == allowed_ip:
                    return True
        return False
    except ValueError:
        return False


def require_germline_access(
    table_name: str, token_info: Optional[TokenInfo]
) -> TokenInfo:
    """
    Check if access to germline table is allowed.
    Raises HTTPException if access denied.
    """
    if table_name in GERMLINE_TABLE_REGISTRY:
        if not token_info:
            raise HTTPException(
                status_code=401,
                detail=f"Access to {table_name} requires authentication. Please provide a valid token.",
            )
        return token_info
    return token_info  # Non-germline tables don't need token


def generate_token(length: int = 64) -> str:
    """Generate a secure random token"""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_token():
    """Create a new API token for germline data access"""

    db = SessionLocal()
    token = generate_token()
    expires_at = None

    token_request = TokenCreateRequest(
        expires_in_days=30,
        user_identifier="admin_animesh",
        permissions=["germline_access"],
        description="Admin token for germline access",
    )

    if token_request.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=token_request.expires_in_days
        )

    db_token = ApiToken(
        token=token,
        user_identifier=token_request.user_identifier,
        description=token_request.description,
        expires_at=expires_at,
        permissions=json.dumps(token_request.permissions)
        if token_request.permissions
        else None,
        ip_whitelist=json.dumps(token_request.ip_whitelist)
        if token_request.ip_whitelist
        else None,
    )

    db.add(db_token)
    db.commit()
    db.refresh(db_token)

    return TokenResponse(
        token_id=db_token.token_id,
        token=db_token.token,
        user_identifier=db_token.user_identifier,
        description=db_token.description,
        expires_at=db_token.expires_at,
        created_at=db_token.created_at,
    )
