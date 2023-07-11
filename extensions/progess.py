## TAKEN FROM TWITCH-DL :D


import logging
import time

from collections import deque
from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, NamedTuple, Optional, Deque, Callable

logger = logging.getLogger(__name__)


TaskId = int


def _format_size(value, digits, unit):
    if digits > 0:
        return "{{:.{}f}}{}".format(digits, unit).format(value)
    else:
        return "{{:d}}{}".format(unit).format(value)


def format_size(bytes_, digits=1):
    if bytes_ < 1024:
        return _format_size(bytes_, digits, "B")

    kilo = bytes_ / 1024
    if kilo < 1024:
        return _format_size(kilo, digits, "kB")

    mega = kilo / 1024
    if mega < 1024:
        return _format_size(mega, digits, "MB")

    return _format_size(mega / 1024, digits, "GB")


def format_duration(total_seconds):
    total_seconds = int(total_seconds)
    hours = total_seconds // 3600
    remainder = total_seconds % 3600
    minutes = remainder // 60
    seconds = total_seconds % 60

    if hours:
        return "{} h {} min".format(hours, minutes)

    if minutes:
        return "{} min {} sec".format(minutes, seconds)

    return "{} sec".format(seconds)


def format_time(total_seconds, force_hours=False):
    total_seconds = int(total_seconds)
    hours = total_seconds // 3600
    remainder = total_seconds % 3600
    minutes = remainder // 60
    seconds = total_seconds % 60

    if hours or force_hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    return f"{minutes:02}:{seconds:02}"


@dataclass
class Task:
    id: TaskId
    size: int
    downloaded: int = 0

    def advance(self, size):
        self.downloaded += size


class Sample(NamedTuple):
    downloaded: int
    timestamp: float


@dataclass
class Progress:
    vod_count: int
    progress_txt: Callable
    downloaded: int = 0
    estimated_total: Optional[int] = None
    last_printed: float = field(default_factory=time.time)
    progress_bytes: int = 0
    progress_perc: int = 0
    remaining_time: Optional[int] = None
    speed: Optional[float] = None
    start_time: float = field(default_factory=time.time)
    tasks: Dict[TaskId, Task] = field(default_factory=dict)
    vod_downloaded_count: int = 0
    samples: Deque[Sample] = field(default_factory=lambda: deque(maxlen=100))

    def start(self, task_id: int, size: int):
        if task_id in self.tasks:
            raise ValueError(f"Task {task_id}: cannot start, already started")

        self.tasks[task_id] = Task(task_id, size)
        self._calculate_total()
        self._calculate_progress()
        self.print()

    def advance(self, task_id: int, size: int):
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id}: cannot advance, not started")

        self.downloaded += size
        self.progress_bytes += size
        self.tasks[task_id].advance(size)
        self.samples.append(Sample(self.downloaded, time.time()))
        self._calculate_progress()
        self.print()

    def already_downloaded(self, task_id: int, size: int):
        if task_id in self.tasks:
            raise ValueError(f"Task {task_id}: cannot mark as downloaded, already started")

        self.tasks[task_id] = Task(task_id, size)
        self.progress_bytes += size
        self.vod_downloaded_count += 1
        self._calculate_total()
        self._calculate_progress()
        self.print()

    def abort(self, task_id: int):
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id}: cannot abort, not started")

        del self.tasks[task_id]
        self.progress_bytes = sum(t.downloaded for t in self.tasks.values())

        self._calculate_total()
        self._calculate_progress()
        self.print()

    def end(self, task_id: int):
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id}: cannot end, not started")

        task = self.tasks[task_id]
        if task.size != task.downloaded:
            logger.warn(f"Taks {task_id} ended with {task.downloaded}b downloaded, expected {task.size}b.")

        self.vod_downloaded_count += 1
        self.print()

    def _calculate_total(self):
        self.estimated_total = int(mean(t.size for t in self.tasks.values()) * self.vod_count) if self.tasks else None

    def _calculate_progress(self):
        self.speed = self._calculate_speed()
        self.progress_perc = int(100 * self.progress_bytes / self.estimated_total) if self.estimated_total else 0
        self.remaining_time = int((self.estimated_total - self.progress_bytes) / self.speed) if self.estimated_total and self.speed else None

    def _calculate_speed(self):
        if len(self.samples) < 2:
            return None

        first_sample = self.samples[0]
        last_sample = self.samples[-1]

        size = last_sample.downloaded - first_sample.downloaded
        duration = last_sample.timestamp - first_sample.timestamp

        if duration == 0:
            duration = 1

        return size / duration

    def print(self):
        now = time.time()

        # Don't print more often than 10 times per second
        if now - self.last_printed < 0.1:
            return

        progress = " ".join(
            [
                f"Downloaded {self.vod_downloaded_count}/{self.vod_count} VODs",
                f"<blue>{self.progress_perc}%</blue>",
                f"of <blue>~{format_size(self.estimated_total)}</blue>" if self.estimated_total else "",
                f"at <blue>{format_size(self.speed)}/s</blue>" if self.speed else "",
                f"ETA <blue>{format_time(self.remaining_time)}</blue>" if self.remaining_time is not None else "",
            ]
        )
        self.progress_txt(progress.replace("<blue>", "").replace("</blue>", ""))

        print(f"\r{progress}     ", end="")
        self.last_printed = now
