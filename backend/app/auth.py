from dataclasses import dataclass
from fastapi import Header, HTTPException
import re

@dataclass(frozen=True)
class Identity:
    user: str
    factory_id: str
    role: str

def get_identity(x_demo_user: str | None = Header(None), x_factory_id: str | None = Header(None)) -> Identity:
    # Deterministic demo identity, deliberately not production authentication.
    user = x_demo_user or "demo-engineer"
    roles = {"demo-viewer": "viewer", "demo-technician": "technician", "demo-manager": "manager", "demo-admin": "admin"}
    factory_id = x_factory_id or "demo-factory"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", factory_id):
        raise HTTPException(400, "factory_id tidak valid")
    return Identity(user, factory_id, roles.get(user, "engineer"))

def require_role(identity: Identity, roles) -> Identity:
    """Guard a route by role. Approval is the coordinator's, not the AI's."""
    if identity.role not in roles and identity.role != "admin":
        raise HTTPException(403, f"role '{identity.role}' tidak diizinkan untuk tindakan ini")
    return identity
