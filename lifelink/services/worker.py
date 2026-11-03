"""SERVICE: background matching workers (MULTITHREADING + producer/consumer queue).

The web thread (producer) puts a request id into a PriorityQueue and returns
immediately. N worker threads (consumers) pick requests - critical ones first -
find compatible donors and create notifications. Each worker owns its own DB
connection because SQLite connections must not be shared between threads."""
import itertools
import logging
import queue
import threading
import time

from ..db import connect
from ..models import notification_model, request_model, user_model
from . import matching

log = logging.getLogger("lifelink.worker")
_queue = queue.PriorityQueue()
_counter = itertools.count()          # tie-breaker keeps FIFO order inside a priority
_threads = []


def enqueue(request_id, urgency):
    _queue.put((matching.URGENCY_PRIORITY[urgency], next(_counter), request_id))


def process_request(db, request_id, gap_days, delay=0.0):
    """Core matching job. Separate from the thread loop so tests can call it directly."""
    req = request_model.get(db, request_id)
    if req is None or req["status"] in ("cancelled", "fulfilled"):
        return 0
    request_model.set_status(db, request_id, "matching")
    time.sleep(delay)   # simulates SMS-gateway latency
    donors = user_model.find_eligible_donors(
        db, matching.compatible_donor_groups(req["blood_group"]), req["city"], gap_days)
    message = matching.build_message(req)
    for donor in donors:
        notification_model.create(db, request_id, donor["id"], message)
    db.commit()
    request_model.set_status(db, request_id, "open", notified_count=len(donors))
    log.info("Request %s matched, %s donor(s) notified", request_id, len(donors))
    return len(donors)


def _loop(db_path, gap_days, delay, stop_event):
    db = connect(db_path)                       # one connection per thread
    while not stop_event.is_set():
        try:
            _prio, _n, request_id = _queue.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            process_request(db, request_id, gap_days, delay)
        except Exception:                       # never let a worker thread die
            log.exception("Worker failed on request %s", request_id)
        finally:
            _queue.task_done()
    db.close()


def start_workers(app):
    """Start worker threads and re-queue unfinished requests (crash recovery)."""
    cfg = app.config
    stop_event = threading.Event()
    for i in range(cfg["WORKER_THREADS"]):
        t = threading.Thread(
            target=_loop, name=f"match-worker-{i+1}", daemon=True,
            args=(cfg["DATABASE_PATH"], cfg["DONATION_GAP_DAYS"], cfg["NOTIFY_DELAY_SECONDS"], stop_event))
        t.start()
        _threads.append(t)
    db = connect(cfg["DATABASE_PATH"])
    for row in request_model.list_pending(db):
        enqueue(row["id"], row["urgency"])
    db.close()
    app.worker_stop_event = stop_event
    log.info("Started %s matching worker thread(s)", cfg["WORKER_THREADS"])


def active_thread_count():
    return sum(1 for t in _threads if t.is_alive())
