from typing import Optional

from celery import Task
from celery.result import AsyncResult


class ProgressRecorder:
    task: Optional[Task]

    def set_current_task(self, task: Task) -> None:
        self.task = task

    def set_progress(
        self, current_step: str, start_time: int, total_time: float
    ) -> None:
        if self.task is None:
            return
        state = AsyncResult(self.task.request.id).state
        if state != "STARTED":
            return
        # The meta object matches VISKAR's JobProgress class
        self.task.update_state(
            state=state,
            meta={
                "currentStep": current_step,
                "startTime": start_time,
                "totalTime": total_time,
            },
        )
