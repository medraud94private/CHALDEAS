"""
Content Report model for user-submitted quality reports.
Allows users to flag incorrect, suspicious, or low-quality content.
"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Index, CheckConstraint
)
from sqlalchemy.sql import func

from app.models.base import Base


class ContentReport(Base):
    """
    User-submitted report for content quality issues.

    entity_type: 'person', 'event', 'location', 'source'
    report_type: 'incorrect', 'suspicious', 'low_quality', 'inappropriate', 'other'
    status: 'pending', 'reviewed', 'accepted', 'rejected'
    """
    __tablename__ = "content_reports"

    id = Column(Integer, primary_key=True, index=True)

    # What content is being reported
    entity_type = Column(
        String(50),
        CheckConstraint(
            "entity_type IN ('person', 'event', 'location', 'source')"
        ),
        nullable=False,
        index=True
    )
    entity_id = Column(Integer, nullable=False, index=True)

    # What field is problematic (optional)
    field_name = Column(String(100))  # e.g., 'biography', 'description', 'name'

    # Report details
    report_type = Column(
        String(50),
        CheckConstraint(
            "report_type IN ('incorrect', 'suspicious', 'low_quality', 'inappropriate', 'other')"
        ),
        nullable=False,
        default='incorrect'
    )

    reason = Column(Text)  # User's explanation
    suggested_correction = Column(Text)  # Optional correction

    # Reporter info (anonymous allowed)
    reporter_ip = Column(String(50))  # For rate limiting
    reporter_session = Column(String(100))  # Browser session ID

    # Status tracking
    status = Column(
        String(50),
        CheckConstraint(
            "status IN ('pending', 'reviewed', 'accepted', 'rejected')"
        ),
        default='pending',
        index=True
    )

    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    review_notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_content_report_entity', 'entity_type', 'entity_id'),
        Index('idx_content_report_status', 'status', 'created_at'),
    )

    def __repr__(self):
        return f"<ContentReport({self.entity_type}:{self.entity_id}, type={self.report_type}, status={self.status})>"
