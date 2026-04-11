from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable


async def run_collection_cycle(
    repository,
    collector,
    notifier,
    *,
    logger: logging.Logger,
) -> bool:
    run = repository.start_collection_run()
    logger.info("Ciclo de coleta iniciado. run_id=%s", run.id)
    try:
        report = await collector.collect_new_jobs_report()
        repository.finish_collection_run(
            run.id,
            status="success",
            jobs_seen=report.jobs_seen,
            jobs_saved=report.jobs_saved,
            errors=report.errors,
        )
    except Exception as exc:
        repository.finish_collection_run(
            run.id,
            status="error",
            jobs_seen=0,
            jobs_saved=0,
            errors=1,
        )
        logger.exception("Falha no ciclo de coleta.")
        await notifier.send_text(f"Falha no ciclo de coleta: {exc}")
        return False

    jobs = list(report.jobs)
    if not jobs:
        await notifier.send_text("Nenhuma vaga nova passou na triagem de hoje.")
        return False
    await notifier.notify_jobs_for_review(jobs)
    return True


async def wait_for_review_window(
    *,
    enable_telegram: bool,
    grace_seconds: int,
    logger: logging.Logger,
) -> None:
    if not enable_telegram:
        return
    if grace_seconds <= 0:
        return
    logger.info("Aguardando callbacks do Telegram por %ss antes de encerrar.", grace_seconds)
    await asyncio.sleep(grace_seconds)


async def run_scheduler(
    *,
    collection_time: str,
    run_collection_cycle: Callable[[], Awaitable[bool]],
    logger: logging.Logger,
) -> None:
    hour_text, minute_text = collection_time.split(":")
    target_hour = int(hour_text)
    target_minute = int(minute_text)

    while True:
        now = datetime.now()
        run_at = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if run_at <= now:
            run_at += timedelta(days=1)
        delay_seconds = max(1, int((run_at - now).total_seconds()))
        logger.info("Proxima coleta agendada para %s", run_at.isoformat(timespec="minutes"))
        await asyncio.sleep(delay_seconds)
        await run_collection_cycle()


async def run_fixed_cycles(
    *,
    cycles: int,
    interval_seconds: int,
    run_collection_cycle: Callable[[], Awaitable[bool]],
    wait_for_review_window: Callable[[], Awaitable[None]],
    logger: logging.Logger,
) -> None:
    for cycle_number in range(1, cycles + 1):
        logger.info("Executando ciclo controlado %s/%s.", cycle_number, cycles)
        jobs_sent_for_review = await run_collection_cycle()
        if jobs_sent_for_review:
            await wait_for_review_window()
        if cycle_number < cycles and interval_seconds > 0:
            logger.info("Aguardando %ss antes do proximo ciclo controlado.", interval_seconds)
            await asyncio.sleep(interval_seconds)


async def run_application(
    *,
    run_once: bool,
    fixed_cycles: int | None,
    cycle_interval_seconds: int,
    runtime_guard,
    repository,
    notifier,
    build_execution_summary: Callable[[str], str],
    run_collection_cycle: Callable[[], Awaitable[bool]],
    wait_for_review_window: Callable[[], Awaitable[None]],
    run_fixed_cycles_callback: Callable[[int, int], Awaitable[None]],
    run_scheduler_callback: Callable[[], Awaitable[None]],
    logger: logging.Logger,
) -> None:
    execution_started_at = datetime.now().isoformat(timespec="seconds")
    terminated_processes = runtime_guard.prepare_for_startup()
    interrupted_runs = repository.interrupt_running_collection_runs()
    if terminated_processes:
        logger.info("Startup limpou processos antigos do projeto: %s", terminated_processes)
    if interrupted_runs:
        logger.info("Startup marcou runs presos como interrompidos: %s", interrupted_runs)
    await notifier.start()
    try:
        if run_once:
            jobs_sent_for_review = await run_collection_cycle()
            if jobs_sent_for_review:
                await wait_for_review_window()
            return
        if fixed_cycles is not None:
            await run_fixed_cycles_callback(fixed_cycles, cycle_interval_seconds)
            return
        await run_scheduler_callback()
    finally:
        logger.info("Resumo final da execucao:\n%s", build_execution_summary(execution_started_at))
        await notifier.stop()
        runtime_guard.release()
