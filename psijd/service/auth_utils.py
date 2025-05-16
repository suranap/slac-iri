from fastapi import Header, HTTPException


def get_bearer_token(
    authorization: str = Header(None, description="Bearer token for API authentication")
) -> str:
    """
    Extracts and validates the Bearer token from the Authorization header.
    Raises HTTPException if the header is missing, malformed, or not a Bearer token.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>'")
    return parts[1]