from sqlalchemy import select
from sqlalchemy.orm import Session
from . import models

def one_or_404(db: Session, model, ident: str, factory_id: str):
    obj = db.scalar(select(model).where(model.id == ident, model.factory_id == factory_id))
    if not obj: raise ValueError("not_found")
    return obj

def audit(db, identity, request_id, action, resource_type, resource_id, before=None, after=None):
    db.add(models.AuditEvent(factory_id=identity.factory_id, actor=identity.user, action=action, resource_type=resource_type, resource_id=resource_id, request_id=request_id, before_json=before, after_json=after))
