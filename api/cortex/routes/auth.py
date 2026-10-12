"""Account endpoints: register, login, logout, current user."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from cortex import accounts

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str
    display_name: str | None = None


def _client(request: Request) -> str:
    return request.client.host if request.client else ""


def _bearer(request: Request) -> str:
    return request.headers.get("authorization", "").partition(" ")[2]


@router.post("/register", status_code=201)
async def register(body: Credentials) -> dict:
    try:
        user, token = await accounts.register(body.email, body.password, body.display_name)
    except accounts.AccountError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    return {"token": token, "user": user}


@router.post("/login")
async def login(body: Credentials, request: Request) -> dict:
    try:
        user, token = await accounts.login(body.email, body.password, _client(request))
    except accounts.AccountError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    return {"token": token, "user": user}


@router.post("/logout", status_code=204)
async def logout(request: Request) -> None:
    await accounts.revoke(_bearer(request))


@router.get("/me")
async def me(request: Request) -> dict:
    """The signed-in account. A configured service token has no account row."""
    user = await accounts.user_for_token(_bearer(request))
    if user is None:
        u = request.state.user
        return {"user": {"id": u, "email": None, "display_name": u}}
    return {"user": user}
