"""
Content Report API - 사용자 콘텐츠 품질 신고
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.models.content_report import ContentReport

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportCreate(BaseModel):
    entity_type: str = Field(..., pattern="^(person|event|location|source)$")
    entity_id: int
    field_name: Optional[str] = None
    report_type: str = Field(default="incorrect", pattern="^(incorrect|suspicious|low_quality|inappropriate|other)$")
    reason: str = Field(..., min_length=10, max_length=2000)
    suggested_correction: Optional[str] = Field(None, max_length=2000)


class ReportResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    report_type: str
    status: str
    message: str


@router.post("/", response_model=ReportResponse)
def create_report(
    report: ReportCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Submit a content quality report.

    Anonymous submissions allowed, but rate-limited by IP.
    """
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else None

    # Check rate limit (max 10 reports per IP per hour)
    if client_ip:
        from sqlalchemy import func
        from datetime import datetime, timedelta

        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_count = db.query(func.count(ContentReport.id)).filter(
            ContentReport.reporter_ip == client_ip,
            ContentReport.created_at > one_hour_ago
        ).scalar()

        if recent_count >= 10:
            raise HTTPException(
                status_code=429,
                detail="Too many reports. Please try again later."
            )

    # Check for duplicate report
    existing = db.query(ContentReport).filter(
        ContentReport.entity_type == report.entity_type,
        ContentReport.entity_id == report.entity_id,
        ContentReport.reporter_ip == client_ip,
        ContentReport.status == 'pending'
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending report for this content."
        )

    # Create report
    db_report = ContentReport(
        entity_type=report.entity_type,
        entity_id=report.entity_id,
        field_name=report.field_name,
        report_type=report.report_type,
        reason=report.reason,
        suggested_correction=report.suggested_correction,
        reporter_ip=client_ip,
        status='pending'
    )

    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    return ReportResponse(
        id=db_report.id,
        entity_type=db_report.entity_type,
        entity_id=db_report.entity_id,
        report_type=db_report.report_type,
        status=db_report.status,
        message="Report submitted successfully. Thank you for your feedback!"
    )


@router.get("/stats")
def get_report_stats(db: Session = Depends(get_db)):
    """Get report statistics (admin)."""
    from sqlalchemy import func

    stats = db.query(
        ContentReport.status,
        func.count(ContentReport.id).label('count')
    ).group_by(ContentReport.status).all()

    return {s.status: s.count for s in stats}
