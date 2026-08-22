from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import NoResultFound
from uuid import uuid4

def error_response(request: Request, code: str, message: str, status: int, details=None):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details or [], "request_id": getattr(request.state, "request_id", str(uuid4()))}})

async def validation_handler(request: Request, exc: ValidationError):
    details = [{"field": ".".join(str(x) for x in e["loc"]), "reason": e["msg"]} for e in exc.errors()]
    return error_response(request, "VALIDATION_ERROR", "Input tidak valid", 422, details)
