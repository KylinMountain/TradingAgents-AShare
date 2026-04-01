import asyncio

from api import main


def _reset_queue_state(limit: int) -> None:
    main._scheduled_analysis_max_concurrency = limit
    main._scheduled_analysis_semaphore = asyncio.Semaphore(limit)
    main._scheduled_analysis_queue_lock = asyncio.Lock()
    main._scheduled_analysis_waiting_job_ids = []
    main._scheduled_analysis_running_job_ids = set()


def test_scheduled_analysis_slot_queues_when_limit_is_full():
    async def scenario():
        _reset_queue_state(1)
        entered = []
        release_first = asyncio.Event()
        first_started = asyncio.Event()

        async def first():
            async with main._scheduled_analysis_slot("job-first", "300750.SZ"):
                entered.append("job-first")
                first_started.set()
                await release_first.wait()

        async def second():
            await first_started.wait()
            async with main._scheduled_analysis_slot("job-second", "600519.SH"):
                entered.append("job-second")

        first_task = asyncio.create_task(first())
        second_task = asyncio.create_task(second())

        await first_started.wait()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert entered == ["job-first"]
        assert main._scheduled_analysis_waiting_job_ids == ["job-second"]
        assert "job-first" in main._scheduled_analysis_running_job_ids
        assert main._get_job("job-second")["waiting_ahead_count"] == 0
        assert main._get_job("job-second")["scheduled_running_count"] == 1
        assert main._get_job("job-second")["scheduled_concurrency_limit"] == 1

        release_first.set()
        await asyncio.gather(first_task, second_task)

        assert entered == ["job-first", "job-second"]
        assert main._scheduled_analysis_waiting_job_ids == []
        assert main._scheduled_analysis_running_job_ids == set()

    asyncio.run(scenario())


def test_scheduled_analysis_slot_respects_max_concurrency():
    async def scenario():
        _reset_queue_state(2)
        in_flight = 0
        max_in_flight = 0
        gate = asyncio.Event()

        async def worker(job_id: str):
            nonlocal in_flight, max_in_flight
            async with main._scheduled_analysis_slot(job_id, job_id):
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
                await gate.wait()
                in_flight -= 1

        tasks = [asyncio.create_task(worker(f"job-{i}")) for i in range(3)]
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert max_in_flight == 2
        assert len(main._scheduled_analysis_waiting_job_ids) == 1

        gate.set()
        await asyncio.gather(*tasks)

    asyncio.run(scenario())
