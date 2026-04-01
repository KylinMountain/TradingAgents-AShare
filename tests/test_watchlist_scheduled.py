"""Test watchlist and scheduled analysis services."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.services import watchlist_service, scheduled_service


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestWatchlist:
    def test_add_and_list(self, db):
        watchlist_service.add_watchlist_item(db, "user1", "300750.SZ")
        items = watchlist_service.list_watchlist(db, "user1")
        assert len(items) == 1
        assert items[0]["symbol"] == "300750.SZ"

    def test_duplicate_rejected(self, db):
        watchlist_service.add_watchlist_item(db, "user1", "300750.SZ")
        with pytest.raises(ValueError, match="已在自选列表中"):
            watchlist_service.add_watchlist_item(db, "user1", "300750.SZ")

    def test_max_limit(self, db):
        for i in range(50):
            watchlist_service.add_watchlist_item(db, "user1", f"{600000 + i}.SH")
        with pytest.raises(ValueError, match="上限"):
            watchlist_service.add_watchlist_item(db, "user1", "000001.SZ")

    def test_delete(self, db):
        item = watchlist_service.add_watchlist_item(db, "user1", "300750.SZ")
        assert watchlist_service.delete_watchlist_item(db, "user1", item["id"])
        assert len(watchlist_service.list_watchlist(db, "user1")) == 0

    def test_user_isolation(self, db):
        watchlist_service.add_watchlist_item(db, "user1", "300750.SZ")
        watchlist_service.add_watchlist_item(db, "user2", "600519.SH")
        assert len(watchlist_service.list_watchlist(db, "user1")) == 1
        assert len(watchlist_service.list_watchlist(db, "user2")) == 1

    def test_has_scheduled_flag(self, db):
        watchlist_service.add_watchlist_item(db, "user1", "300750.SZ")
        watchlist_service.add_watchlist_item(db, "user1", "600519.SH")
        scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        items = watchlist_service.list_watchlist(db, "user1")
        by_symbol = {i["symbol"]: i for i in items}
        assert by_symbol["300750.SZ"]["has_scheduled"] is True
        assert by_symbol["600519.SH"]["has_scheduled"] is False

    def test_batch_add_returns_per_item_results(self, db):
        results = watchlist_service.add_watchlist_items(
            db,
            "user1",
            ["300750.SZ", "600519.SH"],
        )
        assert [item["status"] for item in results] == ["added", "added"]
        assert len(watchlist_service.list_watchlist(db, "user1")) == 2

    def test_batch_add_marks_duplicates(self, db):
        watchlist_service.add_watchlist_item(db, "user1", "300750.SZ")
        results = watchlist_service.add_watchlist_items(
            db,
            "user1",
            ["300750.SZ", "600519.SH", "600519.SH"],
        )
        assert [item["status"] for item in results] == ["duplicate", "added", "duplicate"]

    def test_batch_add_marks_limit_failures(self, db):
        for i in range(49):
            watchlist_service.add_watchlist_item(db, "user1", f"{600000 + i}.SH")
        results = watchlist_service.add_watchlist_items(
            db,
            "user1",
            ["300750.SZ", "000001.SZ"],
        )
        assert results[0]["status"] == "added"
        assert results[1]["status"] == "failed"
        assert "上限" in results[1]["message"]


class TestScheduled:
    def test_create_and_list(self, db):
        scheduled_service.create_scheduled(db, "user1", "300750.SZ", "short")
        items = scheduled_service.list_scheduled(db, "user1")
        assert len(items) == 1
        assert items[0]["horizon"] == "short"
        assert items[0]["trigger_time"] == "20:00"

    def test_create_with_custom_time(self, db):
        scheduled_service.create_scheduled(db, "user1", "300750.SZ", "medium", "07:30")
        items = scheduled_service.list_scheduled(db, "user1")
        assert items[0]["trigger_time"] == "07:30"
        assert items[0]["horizon"] == "medium"

    def test_reject_daytime_hours(self, db):
        with pytest.raises(ValueError, match="20:00"):
            scheduled_service.create_scheduled(db, "user1", "300750.SZ", "short", "10:30")
        with pytest.raises(ValueError, match="20:00"):
            scheduled_service.create_scheduled(db, "user1", "300750.SZ", "short", "15:00")

    def test_allow_boundary_times(self, db):
        # 08:00 is the boundary, should be OK
        scheduled_service.create_scheduled(db, "user1", "300750.SZ", "short", "08:00")
        # 20:00 is the start, should be OK
        scheduled_service.create_scheduled(db, "user1", "600519.SH", "short", "20:00")
        # Midnight should be OK
        scheduled_service.create_scheduled(db, "user1", "000001.SZ", "short", "00:30")

    def test_duplicate_rejected(self, db):
        scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        with pytest.raises(ValueError, match="已有定时分析"):
            scheduled_service.create_scheduled(db, "user1", "300750.SZ")

    def test_invalid_horizon(self, db):
        with pytest.raises(ValueError, match="horizon"):
            scheduled_service.create_scheduled(db, "user1", "300750.SZ", "long")

    def test_max_limit(self, db):
        for i in range(10):
            scheduled_service.create_scheduled(db, "user1", f"{600000 + i}.SH")
        with pytest.raises(ValueError, match="上限"):
            scheduled_service.create_scheduled(db, "user1", "000001.SZ")

    def test_update_horizon(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ", "short")
        updated = scheduled_service.update_scheduled(db, "user1", item["id"], horizon="medium")
        assert updated["horizon"] == "medium"

    def test_update_trigger_time(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        updated = scheduled_service.update_scheduled(db, "user1", item["id"], trigger_time="21:30")
        assert updated["trigger_time"] == "21:30"

    def test_batch_update_horizon_and_time(self, db):
        first = scheduled_service.create_scheduled(db, "user1", "300750.SZ", "short", "20:00")
        second = scheduled_service.create_scheduled(db, "user1", "600519.SH", "short", "20:00")

        items = scheduled_service.batch_update_scheduled(
            db,
            "user1",
            [first["id"], second["id"]],
            horizon="medium",
            trigger_time="21:30",
        )

        assert [item["horizon"] for item in items] == ["medium", "medium"]
        assert [item["trigger_time"] for item in items] == ["21:30", "21:30"]

    def test_batch_update_active_resets_failures(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        scheduled_service.mark_run_failed(db, item["id"], "2026-03-21")

        items = scheduled_service.batch_update_scheduled(
            db,
            "user1",
            [item["id"]],
            is_active=True,
        )

        assert items[0]["is_active"] is True
        assert items[0]["consecutive_failures"] == 0

    def test_batch_update_rejects_invalid_ids(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        with pytest.raises(ValueError, match="失效"):
            scheduled_service.batch_update_scheduled(
                db,
                "user1",
                [item["id"], "missing-id"],
                horizon="medium",
            )

    def test_update_reject_daytime(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        with pytest.raises(ValueError, match="20:00"):
            scheduled_service.update_scheduled(db, "user1", item["id"], trigger_time="11:00")

    def test_mark_success(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        scheduled_service.mark_run_success(db, item["id"], "2026-03-21", "report-123")
        items = scheduled_service.list_scheduled(db, "user1")
        assert items[0]["last_run_status"] == "success"
        assert items[0]["last_report_id"] == "report-123"

    def test_mark_failed_auto_deactivate(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        for day in range(1, 4):
            scheduled_service.mark_run_failed(db, item["id"], f"2026-03-{20 + day}")
        items = scheduled_service.list_scheduled(db, "user1")
        assert items[0]["is_active"] is False
        assert items[0]["consecutive_failures"] == 3

    def test_record_manual_test_result_keeps_schedule_window_available(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        scheduled_service.record_manual_test_result(db, item["id"], "success", "manual-report")
        items = scheduled_service.list_scheduled(db, "user1")
        assert items[0]["last_run_status"] == "success"
        assert items[0]["last_report_id"] == "manual-report"
        assert items[0]["last_run_date"] is None

    def test_reactivate_resets_failures(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        scheduled_service.mark_run_failed(db, item["id"], "2026-03-21")
        scheduled_service.update_scheduled(db, "user1", item["id"], is_active=True)
        items = scheduled_service.list_scheduled(db, "user1")
        assert items[0]["consecutive_failures"] == 0

    def test_get_pending_tasks_respects_trigger_time(self, db):
        scheduled_service.create_scheduled(db, "user1", "300750.SZ", "short", "20:00")
        scheduled_service.create_scheduled(db, "user1", "600519.SH", "short", "22:00")
        # At 20:30, only the 20:00 task should be pending
        tasks = scheduled_service.get_pending_tasks(db, "2026-03-21", "20:30")
        assert len(tasks) == 1
        assert tasks[0].symbol == "300750.SZ"
        # At 22:00, both should be pending
        tasks2 = scheduled_service.get_pending_tasks(db, "2026-03-21", "22:00")
        assert len(tasks2) == 2

    def test_get_pending_skips_already_run(self, db):
        scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        tasks = scheduled_service.get_pending_tasks(db, "2026-03-21", "23:59")
        scheduled_service.mark_run_success(db, tasks[0].id, "2026-03-21", "r1")
        tasks2 = scheduled_service.get_pending_tasks(db, "2026-03-21", "23:59")
        assert len(tasks2) == 0

    def test_delete(self, db):
        item = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        assert scheduled_service.delete_scheduled(db, "user1", item["id"])
        assert len(scheduled_service.list_scheduled(db, "user1")) == 0

    def test_batch_delete(self, db):
        first = scheduled_service.create_scheduled(db, "user1", "300750.SZ")
        second = scheduled_service.create_scheduled(db, "user1", "600519.SH")

        result = scheduled_service.batch_delete_scheduled(db, "user1", [first["id"], second["id"]])

        assert result["deleted_ids"] == [first["id"], second["id"]]
        assert result["missing_ids"] == []
        assert scheduled_service.list_scheduled(db, "user1") == []
