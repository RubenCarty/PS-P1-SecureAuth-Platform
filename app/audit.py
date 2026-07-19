import hashlib
import hmac
import json

from flask import current_app, g, request, session

from .extensions import db
from .models import AuditLog


def _hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    key = current_app.config["AUDIT_HMAC_KEY"].encode("utf-8")
    return hmac.new(key, ip.encode("utf-8"), hashlib.sha256).hexdigest()


def audit_event(
    action: str,
    *,
    success: bool = True,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    details: dict | None = None,
) -> None:
    user = session.get("user", {})
    safe_details = json.dumps(details or {}, ensure_ascii=False, separators=(",", ":"))[:1000]
    entry = AuditLog(
        request_id=getattr(g, "request_id", "unknown"),
        user_oid=user.get("oid"),
        username=user.get("username"),
        action=action[:80],
        resource_type=(resource_type or "")[:50] or None,
        resource_id=(str(resource_id) if resource_id is not None else None),
        success=success,
        ip_hash=_hash_ip(request.remote_addr),
        user_agent=request.user_agent.string[:300],
        details=safe_details,
    )
    try:
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("No se pudo guardar auditoría action=%s", action)
