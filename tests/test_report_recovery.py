from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, ReportDB
from api.services import report_service


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _add_report(
    db,
    *,
    status: str = "running",
    decision=None,
    final_trade_decision=None,
    result_data=None,
):
    now = datetime.now(timezone.utc)
    report = ReportDB(
        id=uuid4().hex,
        user_id=uuid4().hex,
        symbol="600519.SH",
        trade_date="2026-04-01",
        status=status,
        decision=decision,
        final_trade_decision=final_trade_decision,
        result_data=result_data,
        created_at=now,
        updated_at=now,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def test_recover_stale_active_reports_marks_empty_running_report_failed():
    db = _make_session()
    try:
        report = _add_report(db, status="running")

        result = report_service.recover_stale_active_reports(db)

        refreshed = db.query(ReportDB).filter(ReportDB.id == report.id).first()
        assert result == {"total": 1, "completed": 0, "failed": 1}
        assert refreshed is not None
        assert refreshed.status == "failed"
        assert refreshed.error == report_service.STALE_REPORT_ERROR_MESSAGE
    finally:
        db.close()


def test_recover_stale_active_reports_marks_partial_running_report_failed():
    db = _make_session()
    try:
        report = _add_report(
            db,
            status="running",
            final_trade_decision="结论：持有\n目标价：1750\n止损价：1650",
            result_data={"final_trade_decision": "结论：持有"},
        )

        result = report_service.recover_stale_active_reports(db)

        refreshed = db.query(ReportDB).filter(ReportDB.id == report.id).first()
        assert result == {"total": 1, "completed": 0, "failed": 1}
        assert refreshed is not None
        assert refreshed.status == "failed"
        assert refreshed.error == report_service.STALE_REPORT_ERROR_MESSAGE
    finally:
        db.close()


def test_finalize_orphan_report_marks_pending_report_failed():
    db = _make_session()
    try:
        report = _add_report(db, status="pending")

        refreshed = report_service.finalize_orphan_report(db, report)

        assert refreshed.status == "failed"
        assert refreshed.error == report_service.STALE_REPORT_ERROR_MESSAGE
    finally:
        db.close()
