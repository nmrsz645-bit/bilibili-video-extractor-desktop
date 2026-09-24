"""正在运行的提取任务使用的进程内暂停闸门。"""
import asyncio
import threading


class PauseGate:
    def __init__(self):
        self._resumed = threading.Event()
        self._resumed.set()
        self._waiting = threading.Event()

    def pause(self):
        self._waiting.clear()
        self._resumed.clear()

    def resume(self):
        self._resumed.set()
        self._waiting.clear()

    @property
    def paused(self) -> bool:
        return not self._resumed.is_set()

    @property
    def waiting(self) -> bool:
        return self._waiting.is_set()

    async def checkpoint(self):
        if self._resumed.is_set():
            return
        try:
            while not self._resumed.is_set():
                self._waiting.set()
                await asyncio.sleep(0.1)
        finally:
            self._waiting.clear()
