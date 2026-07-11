import re
from typing import Any, Optional

from sqlalchemy import func

from app.extensions import db
from app.models.church import Church


def normalize_church_name(church_input: Any) -> Optional[str]:
    if church_input is None:
        return None

    value = str(church_input).strip()
    if not value:
        return None

    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^A-Za-z0-9\s&'.,()/-]", "", value).strip()
    if not value or value.lower() == "other":
        return None

    return value.title()


def resolve_church_id(church_input: Any) -> Optional[int]:
    if church_input is None:
        return None

    try:
        church_id = int(church_input)
        church = Church.query.get(church_id)
        return church.id if church else None
    except (TypeError, ValueError):
        pass

    normalized_name = normalize_church_name(church_input)
    if not normalized_name:
        return None

    church = Church.query.filter(
        func.lower(Church.name) == normalized_name.lower()
    ).first()
    if not church:
        church = Church(name=normalized_name)
        db.session.add(church)
        db.session.flush()

    return church.id
