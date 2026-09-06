"""Background media generation, decoupled from the turn that asks for it.

Generation is slow -- SDRunnerClient.generate_image() polls for the output file
up to its timeout -- and a tutor should not stop talking while a picture is
drawn. Modules hand a request to this service and carry on; the picture arrives
later as an event.

Deliberately Qt-free. Events fire on this service's worker thread, and the UI
layer is responsible for marshalling them onto its own -- which is what keeps
modules and this service testable without a display.
"""

import itertools
import threading
import time
from dataclasses import dataclass
from enum import IntEnum, auto, Enum
from pathlib import Path
from typing import Any, Callable, Optional

from utils.logging_setup import get_logger

logger = get_logger(__name__)

IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "webp")

#: How many finished jobs to remember for wait_for(). Only the current item is
#: ever waited on, so this needs to cover a burst of pre-generation, not a
#: whole session.
_MAX_REMEMBERED_RESULTS = 256


class MediaPriority(IntEnum):
    """Lower runs first.

    NOW is what the learner is looking at; AHEAD is pre-generation for a lesson
    plan's later items, which must never make the current one wait.
    """
    NOW = 0
    AHEAD = 1


class MediaState(Enum):
    QUEUED = auto()
    RUNNING = auto()
    READY = auto()
    FAILED = auto()
    CANCELLED = auto()


_TERMINAL_STATES = frozenset(
    {MediaState.READY, MediaState.FAILED, MediaState.CANCELLED})


@dataclass(frozen=True)
class MediaEvent:
    """What happened to one request.

    *priority* travels with the event so a consumer can tell the item being
    waited on from one drawn ahead of time -- a UI must not put "generating"
    over a good picture because the next word started rendering.
    """
    job_id: int
    slug: str
    state: MediaState
    path: Optional[str] = None
    group: Optional[str] = None
    error: Optional[str] = None
    priority: MediaPriority = MediaPriority.NOW


@dataclass
class _Job:
    job_id: int
    slug: str
    prompt: str
    cache_dir: Path
    group: Optional[str]
    priority: MediaPriority
    sequence: int
    cancelled: bool = False


def find_cached(cache_dir: Path, slug: str) -> Optional[str]:
    """Path of an already-generated file for *slug*, or None.

    Synchronous on purpose: a cache hit is a file-existence check, and making
    the common case wait on a worker would add latency to answer with a file
    that is already there.
    """
    for extension in IMAGE_EXTENSIONS:
        candidate = Path(cache_dir) / f"{slug}.{extension}"
        if candidate.exists():
            return str(candidate)
    return None


class MediaGenerationService:
    """Serialises generation requests onto a single background worker.

    Serial rather than pooled because the requests land on one GPU pipeline:
    running two at once finishes neither sooner and makes the one being waited
    on slower.
    """

    def __init__(self, sd_client: Any = None, cache_dir: Optional[Path] = None):
        self._sd_client = sd_client
        self._default_cache_dir = Path(cache_dir) if cache_dir else None
        self._pending: dict = {}          # slug -> _Job
        self._running_job: Optional[_Job] = None
        self._listeners: list = []
        self._sequence = itertools.count()
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)
        self._shutdown = False
        self._worker: Optional[threading.Thread] = None
        # Terminal events, so wait_for() works whether it is called before or
        # after the job finishes. Bounded: a long session would otherwise
        # accumulate one entry per picture for its whole life.
        self._terminal: dict = {}

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    def add_listener(self, listener: Callable[[MediaEvent], None]) -> None:
        """Register a callback for every event. Called on the worker thread."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[MediaEvent], None]) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _emit(self, event: MediaEvent) -> None:
        if event.state in _TERMINAL_STATES:
            self._record_terminal(event)
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                # One bad listener must not stop the queue or the others.
                logger.warning(f"Media listener failed for {event.slug!r}: {e}")

    def _record_terminal(self, event: MediaEvent) -> None:
        with self._wake:
            self._terminal[event.job_id] = event
            while len(self._terminal) > _MAX_REMEMBERED_RESULTS:
                self._terminal.pop(next(iter(self._terminal)))
            self._wake.notify_all()

    def wait_for(self, job_id: Optional[int], timeout: Optional[float] = None) -> Optional[str]:
        """Block until *job_id* finishes, returning its path or None.

        For the item the learner is looking at right now, where the module's
        own wording depends on whether a picture exists. Everything else should
        be requested and left to arrive.

        Safe to call after the job has already finished -- the result is
        remembered, so there is no window between requesting and waiting.
        """
        if job_id is None:
            return None
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._wake:
            while job_id not in self._terminal:
                if self._shutdown:
                    return None
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    logger.warning(f"Timed out waiting for media job {job_id}")
                    return None
                self._wake.wait(timeout=remaining if remaining is not None else 1.0)
            event = self._terminal[job_id]
        return event.path if event.state is MediaState.READY else None

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    def request(
        self,
        slug: str,
        prompt: str,
        cache_dir: Optional[Path] = None,
        group: Optional[str] = None,
        priority: MediaPriority = MediaPriority.NOW,
    ) -> Optional[int]:
        """Queue a generation for *slug*, returning its job id.

        A slug already queued or being drawn is not started twice; a queued
        one has its priority raised if this request is more urgent, which is
        what lets a pre-generated item the learner has just reached jump ahead
        of the rest of the plan.

        Returns None when there is nothing to generate with.
        """
        if self._sd_client is None:
            return None
        directory = Path(cache_dir) if cache_dir else self._default_cache_dir
        if directory is None:
            raise ValueError("No cache directory given and no default set")

        with self._wake:
            running = self._running_job
            if (running is not None and running.slug == slug
                    and not running.cancelled):
                # Already being drawn; its READY event answers this caller too.
                return running.job_id
            existing = self._pending.get(slug)
            if existing is not None:
                if priority < existing.priority:
                    existing.priority = priority
                    existing.sequence = next(self._sequence)
                    self._wake.notify_all()
                return existing.job_id
            job = _Job(
                job_id=next(self._ids),
                slug=slug,
                prompt=prompt,
                cache_dir=directory,
                group=group,
                priority=priority,
                sequence=next(self._sequence),
            )
            self._pending[slug] = job
            self._wake.notify_all()
        self._ensure_worker()
        self._emit(MediaEvent(
            job.job_id, slug, MediaState.QUEUED, group=group, priority=job.priority))
        return job.job_id

    def request_ahead(self, items, cache_dir=None, group=None) -> list:
        """Queue several (slug, prompt) pairs for later use.

        Front-loading a lesson plan: the pictures for its later items are drawn
        while the learner works through the earlier ones.
        """
        return [
            self.request(slug, prompt, cache_dir=cache_dir, group=group,
                         priority=MediaPriority.AHEAD)
            for slug, prompt in items
        ]

    def cancel_group(self, group: str) -> None:
        """Drop queued work for *group*.

        A job already running is left to finish -- sd-runner has no cancel --
        but it is marked, so it reports CANCELLED rather than READY and no
        listener acts on a result nobody is waiting for. The file still lands
        in the cache, where a later request for the same slug will find it.
        """
        self._drop(lambda job: job.group == group)

    def cancel_all(self) -> None:
        self._drop(lambda job: True)

    def _drop(self, matches: Callable[[_Job], bool]) -> None:
        dropped = []
        with self._wake:
            for slug, job in list(self._pending.items()):
                if matches(job):
                    job.cancelled = True
                    del self._pending[slug]
                    dropped.append(job)
            if self._running_job is not None and matches(self._running_job):
                # Cannot be stopped, but its result will be reported as
                # cancelled rather than handed to a listener that moved on.
                self._running_job.cancelled = True
            self._wake.notify_all()
        # Emitted outside the lock: a listener that calls back in would
        # otherwise deadlock on a non-reentrant lock.
        for job in dropped:
            self._emit(MediaEvent(
                job.job_id, job.slug, MediaState.CANCELLED, group=job.group,
                priority=job.priority))

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def is_pending(self, slug: str) -> bool:
        with self._lock:
            running = self._running_job.slug if self._running_job else None
            return slug in self._pending or running == slug

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._shutdown:
                return
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run, name="media-generation", daemon=True)
        self._worker.start()

    def _take_next(self) -> Optional[_Job]:
        """Block until there is work, or shutdown. Highest priority, then FIFO."""
        with self._wake:
            while not self._shutdown and not self._pending:
                self._wake.wait(timeout=1.0)
            if self._shutdown or not self._pending:
                return None
            job = min(
                self._pending.values(), key=lambda j: (j.priority, j.sequence))
            del self._pending[job.slug]
            self._running_job = job
            return job

    def _run(self) -> None:
        while not self._shutdown:
            job = self._take_next()
            if job is None:
                continue
            try:
                self._process(job)
            except Exception as e:
                logger.warning(f"Media generation failed for {job.slug!r}: {e}")
                self._emit(MediaEvent(
                    job.job_id, job.slug, MediaState.FAILED,
                    group=job.group, error=str(e), priority=job.priority))
            finally:
                with self._lock:
                    self._running_job = None

    def _process(self, job: _Job) -> None:
        cached = find_cached(job.cache_dir, job.slug)
        if cached:
            self._emit(MediaEvent(
                job.job_id, job.slug, MediaState.READY, path=cached,
                group=job.group, priority=job.priority))
            return

        self._emit(MediaEvent(
            job.job_id, job.slug, MediaState.RUNNING, group=job.group,
            priority=job.priority))
        job.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._sd_client.generate_image(
            positive_prompt=job.prompt,
            target_dir=str(job.cache_dir),
            filename=job.slug,
        )
        if job.cancelled:
            self._emit(MediaEvent(
                job.job_id, job.slug, MediaState.CANCELLED, group=job.group,
                priority=job.priority))
            return
        if path:
            self._emit(MediaEvent(
                job.job_id, job.slug, MediaState.READY, path=path,
                group=job.group, priority=job.priority))
        else:
            self._emit(MediaEvent(
                job.job_id, job.slug, MediaState.FAILED, group=job.group,
                error="generation produced no file", priority=job.priority))

    def shutdown(self, timeout: float = 2.0) -> None:
        """Stop accepting work and let the worker finish what it is on."""
        with self._wake:
            self._shutdown = True
            self._pending.clear()
            # Releases any wait_for() still blocked on a job that will now
            # never run.
            self._wake.notify_all()
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=timeout)
