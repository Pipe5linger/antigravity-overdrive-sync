import asyncio
import logging
from typing import List, Dict, Any
from core.profile_evaluator import ProfileEvaluator

logger = logging.getLogger(__name__)


class SyncDaemon:
    """
    Background sync daemon with non-blocking fast-path triage
    and asynchronous LLM evaluation queue.
    """

    def __init__(self, evaluator: ProfileEvaluator, batch_size: int = 5):
        self.evaluator = evaluator
        self.batch_size = batch_size
        self.queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self._worker_task: asyncio.Task | None = None

    async def start(self):
        """Starts the background LLM worker queue."""
        self.is_running = True
        self._worker_task = asyncio.create_task(self._llm_worker())
        logger.info("[Daemon] Non-blocking LLM background worker initialized.")

    async def stop(self):
        """Gracefully shuts down the background queue."""
        self.is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def process_sync_tick(self, unprofiled_sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main sync tick (Target: < 5ms).
        - Zero-Signal sessions: Marked as profiled instantly.
        - High-Signal sessions: Offloaded to the background queue.
        """
        batch = unprofiled_sessions[: self.batch_size]
        fast_path_count = 0
        queued_count = 0

        for session in batch:
            sess_id = session["session_id"]
            dialogue = session["dialogue"]

            # Fast-path boolean check (<0.1ms)
            if not self.evaluator.fact_extractor.has_signal(dialogue):
                # Instantly clear from unprofiled queue
                self.evaluator.mark_as_profiled(sess_id, extracted_facts=[])
                fast_path_count += 1
            else:
                # Offload to async queue
                await self.queue.put(session)
                queued_count += 1

        return {
            "processed_fast_path": fast_path_count,
            "queued_for_llm": queued_count,
            "queue_depth": self.queue.qsize(),
        }

    async def _llm_worker(self):
        """
        Worker task running perpetually in the background.
        Pulls queued high-signal sessions and executes LLM calls via thread pool.
        """
        while self.is_running:
            session = await self.queue.get()
            sess_id = session.get("session_id")
            dialogue = session.get("dialogue", "")

            try:
                # Offload sync LLM evaluation to a background thread to prevent loop blocking
                await asyncio.to_thread(
                    self.evaluator.evaluate_dialogue,
                    dialogue,
                    session_id=sess_id
                )
            except Exception as e:
                logger.error(f"[Daemon Worker] Error evaluating session {sess_id}: {e}")
            finally:
                self.queue.task_done()