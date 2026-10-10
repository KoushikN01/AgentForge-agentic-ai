"""
Sample FastAPI application used as AgentForge's investigation workspace.

NOTE: See docs/sample-project-bugs.md at the AgentForge project root for
the list of intentional bugs and why each one was introduced.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.auth import InvalidCredentialsError, authenticate, create_access_token
from app.orders import OrderNotFoundError, get_order

app = FastAPI(title="Sample Project", description="AgentForge's investigation sandbox")


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest):
    try:
        user_id = authenticate(payload.email, payload.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user_id)
    return {"access_token": token}


@app.get("/api/orders/{order_id}")
def read_order(order_id: int):
    try:
        return get_order(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Order not found.")
