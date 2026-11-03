# -*- coding: utf-8 -*-
"""命令队列线程：手动指令串行执行，防止串口并发冲突与界面卡顿。"""
import queue

from PyQt5.QtCore import QThread, pyqtSignal


class CommandRunner(QThread):
    log = pyqtSignal(str)
    failed = pyqtSignal(str)
    task_done = pyqtSignal(str)
    queue_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._q = queue.Queue()
        self._stop = False

    def submit(self, desc: str, fn):
        self._q.put((desc, fn))
        self.queue_changed.emit(self._q.qsize())
        self.log.emit(f"已提交: {desc}")

    def clear(self):
        dropped = 0
        while True:
            try:
                self._q.get_nowait()
                dropped += 1
            except queue.Empty:
                break
        if dropped:
            self.queue_changed.emit(0)
            self.log.emit(f"已清空队列中的 {dropped} 条待执行指令")

    def shutdown(self):
        self._stop = True

    def run(self):
        while not self._stop:
            try:
                desc, fn = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            self.queue_changed.emit(self._q.qsize())
            try:
                fn()
                self.task_done.emit(desc)
            except Exception as e:
                self.failed.emit(f"{desc} 失败: {e}")
