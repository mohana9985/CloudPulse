from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import ContactMessage
from app.schemas.contact import ContactCreate


def create_contact_message(db: Session, payload: ContactCreate) -> ContactMessage:
    message = ContactMessage(
        name=payload.name,
        email=str(payload.email),
        subject=payload.subject,
        message=payload.message,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def count_contact_messages(db: Session) -> int:
    return db.scalar(select(func.count(ContactMessage.id))) or 0
