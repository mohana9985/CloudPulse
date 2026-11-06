from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.metrics import CONTACT_MESSAGES_TOTAL
from app.database.connection import get_db
from app.schemas.contact import ContactCreate, ContactOut
from app.services.contact_service import create_contact_message

router = APIRouter(prefix="/api", tags=["Contact"])


@router.post("/contact", response_model=ContactOut, status_code=201)
def submit_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    saved = create_contact_message(db, payload)
    CONTACT_MESSAGES_TOTAL.inc()
    return {
        "id": saved.id,
        "message": "Thank you! Your message has been received.",
        "created_at": saved.created_at,
    }
