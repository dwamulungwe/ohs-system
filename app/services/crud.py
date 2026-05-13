from typing import Any, Optional, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


def list_records(db: Session, model: type[ModelT], *, skip: int = 0, limit: int = 100) -> list[ModelT]:
    statement: Select[tuple[ModelT]] = select(model).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


def get_record_or_none(db: Session, model: type[ModelT], record_id: int) -> Optional[ModelT]:
    return db.get(model, record_id)


def create_record(db: Session, model: type[ModelT], data: dict[str, Any]) -> ModelT:
    record = model(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_record(db: Session, record: ModelT, data: dict[str, Any]) -> ModelT:
    for field, value in data.items():
        setattr(record, field, value)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
