"""Test watchlist and scheduled analysis services."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.services import scheduled_service, watchlist_service


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_window_task(db, symbol: str, slot: str):
    return scheduled_service.create_scheduled(
        db,
        "user1",
        symbol,
        task_type="market_window",
        task_slot=slot,
    )


def _create_custom_task(db, symbol: str, slot: str, **kwargs):
    return scheduled_service.create_scheduled(
        db,
        "user1",
        symbol,
        task_type="custom_recurring",
        task_slot=slot,
        **kwargs,
    )


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

    def test_has_scheduled_flag_and_count(self, db):
        watchlist_service.add_watchlist_item(db, "user1", "300750.SZ")
        watchlist_service.add_watchlist_item(db, "user1", "600519.SH")
        _create_window_task(db, "300750.SZ", "pre_open_0800")
        _create_custom_task(db, "300750.SZ", "custom_short", frequency="daily", trigger_time="20:00")
        items = watchlist_service.list_watchlist(db, "user1")
        by_symbol = {i["symbol"]: i for i in items}
        assert by_symbol["300750.SZ"]["has_scheduled"] is True
        assert by_symbol["300750.SZ"]["scheduled_count"] == 2
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
    def test_create_market_window_task(self, db):
        item = _create_window_task(db, "300750.SZ", "pre_open_0800")
        assert item["task_type"] == "market_window"
        assert item["task_slot"] == "pre_open_0800"
        assert item["trigger_time"] == "08:00"
        assert item["frequency"] == "trading_day"
        assert item["horizon"] == "short"

    def test_create_custom_long_maps_to_medium(self, db):
        item = _create_custom_task(db, "300750.SZ", "custom_long", frequency="daily", trigger_time="07:30")
        assert item["task_type"] == "custom_recurring"
        assert item["horizon"] == "medium"
        assert item["trigger_time"] == "07:30"

    def test_duplicate_slot_rejected(self, db):
        _create_window_task(db, "300750.SZ", "pre_open_0800")
        with pytest.raises(ValueError, match="任务已存在"):
            _create_window_task(db, "300750.SZ", "pre_open_0800")

    def test_same_symbol_can_have_five_slots(self, db):
        _create_window_task(db, "300750.SZ", "pre_open_0800")
        _create_window_task(db, "300750.SZ", "midday_1200")
        _create_window_task(db, "300750.SZ", "post_close_2000")
        _create_custom_task(db, "300750.SZ", "custom_short", frequency="weekly", trigger_time="07:30", day_of_week=0)
        _create_custom_task(db, "300750.SZ", "custom_long", frequency="monthly", trigger_time="20:00", day_of_month=20)
        items = scheduled_service.list_scheduled(db, "user1")
        assert len(items) == 5

    def test_reject_daytime_hours_for_custom_task(self, db):
        with pytest.raises(ValueError, match="12:00"):
            _create_custom_task(db, "300750.SZ", "custom_short", frequency="daily", trigger_time="10:30")

    def test_allow_fixed_midday_boundary(self, db):
        item = _create_window_task(db, "300750.SZ", "midday_1200")
        assert item["trigger_time"] == "12:00"

    def test_update_custom_schedule_fields(self, db):
        item = _create_custom_task(db, "300750.SZ", "custom_short", frequency="daily", trigger_time="20:00")
        updated = scheduled_service.update_scheduled(
            db,
            "user1",
            item["id"],
            frequency="weekly",
            trigger_time="07:30",
            day_of_week=2,
            prompt_mode="override_global",
            custom_prompt="更关注量价和缺口",
        )
        assert updated["frequency"] == "weekly"
        assert updated["day_of_week"] == 2
        assert updated["prompt_mode"] == "override_global"
        assert updated["custom_prompt"] == "更关注量价和缺口"

    def test_update_market_window_only_changes_prompt_fields(self, db):
        item = _create_window_task(db, "300750.SZ", "post_close_2000")
        updated = scheduled_service.update_scheduled(
            db,
            "user1",
            item["id"],
            trigger_time="07:30",
            frequency="weekly",
            prompt_mode="override_global",
            custom_prompt="关注龙虎榜",
        )
        assert updated["trigger_time"] == "20:00"
        assert updated["frequency"] == "trading_day"
        assert updated["prompt_mode"] == "override_global"

    def test_batch_update_active_resets_failures(self, db):
        item = _create_window_task(db, "300750.SZ", "post_close_2000")
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
        item = _create_window_task(db, "300750.SZ", "post_close_2000")
        with pytest.raises(ValueError, match="失效"):
            scheduled_service.batch_update_scheduled(
                db,
                "user1",
                [item["id"], "missing-id"],
                is_active=False,
            )

    def test_mark_success_records_last_run_key(self, db):
        item = _create_custom_task(db, "300750.SZ", "custom_short", frequency="weekly", trigger_time="20:00", day_of_week=4)
        scheduled_service.mark_run_success(db, item["id"], "2026-03-20", "report-123")
        items = scheduled_service.list_scheduled(db, "user1")
        assert items[0]["last_run_status"] == "success"
        assert items[0]["last_report_id"] == "report-123"
        assert items[0]["last_run_key"] == "2026-W12"

    def test_mark_failed_auto_deactivate(self, db):
        item = _create_window_task(db, "300750.SZ", "post_close_2000")
        for day in range(1, 4):
            scheduled_service.mark_run_failed(db, item["id"], f"2026-03-{20 + day}")
        items = scheduled_service.list_scheduled(db, "user1")
        assert items[0]["is_active"] is False
        assert items[0]["consecutive_failures"] == 3

    def test_record_manual_test_result_keeps_schedule_window_available(self, db):
        item = _create_window_task(db, "300750.SZ", "post_close_2000")
        scheduled_service.record_manual_test_result(db, item["id"], "success", "manual-report")
        items = scheduled_service.list_scheduled(db, "user1")
        assert items[0]["last_run_status"] == "success"
        assert items[0]["last_report_id"] == "manual-report"
        assert items[0]["last_run_date"] is None

    def test_get_pending_tasks_respects_custom_frequency(self, db):
        _create_window_task(db, "300750.SZ", "post_close_2000")
        _create_custom_task(db, "300750.SZ", "custom_short", frequency="weekly", trigger_time="07:30", day_of_week=4)
        tasks = scheduled_service.get_pending_tasks(db, "2026-03-20", "20:30")
        slots = {task.task_slot for task in tasks}
        assert "post_close_2000" in slots
        assert "custom_short" in slots

    def test_get_pending_skips_already_run_in_same_period(self, db):
        item = _create_custom_task(db, "300750.SZ", "custom_short", frequency="monthly", trigger_time="20:00", day_of_month=20)
        tasks = scheduled_service.get_pending_tasks(db, "2026-03-20", "20:30")
        assert len(tasks) == 1
        scheduled_service.mark_run_success(db, item["id"], "2026-03-20", "r1")
        tasks2 = scheduled_service.get_pending_tasks(db, "2026-03-20", "20:30")
        assert len(tasks2) == 0

    def test_delete(self, db):
        item = _create_window_task(db, "300750.SZ", "pre_open_0800")
        assert scheduled_service.delete_scheduled(db, "user1", item["id"])
        assert len(scheduled_service.list_scheduled(db, "user1")) == 0

    def test_batch_delete(self, db):
        first = _create_window_task(db, "300750.SZ", "pre_open_0800")
        second = _create_window_task(db, "600519.SH", "post_close_2000")
        result = scheduled_service.batch_delete_scheduled(db, "user1", [first["id"], second["id"]])
        assert result["deleted_ids"] == [first["id"], second["id"]]
        assert result["missing_ids"] == []
        assert scheduled_service.list_scheduled(db, "user1") == []
