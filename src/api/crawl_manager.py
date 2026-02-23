"""Background crawl job manager for SenseBase.

Manages running the full extraction pipeline (discover -> clone -> analyze ->
output -> reload) in a background daemon thread so the webapp stays responsive.
"""

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable


class CrawlStage(str, Enum):
    """Stages of the crawl pipeline."""

    IDLE = "idle"
    DISCOVER = "discover"
    CLONE = "clone"
    ANALYZE = "analyze"
    OUTPUT = "output"
    RELOADING = "reloading"
    COMPLETED = "completed"
    FAILED = "failed"


STAGE_ORDER = [
    CrawlStage.DISCOVER,
    CrawlStage.CLONE,
    CrawlStage.ANALYZE,
    CrawlStage.OUTPUT,
    CrawlStage.RELOADING,
]


@dataclass
class CrawlJob:
    """Represents a single crawl pipeline run."""

    job_id: str
    status: str = "idle"  # idle | running | completed | failed
    current_stage: str = CrawlStage.IDLE.value
    stage_index: int = -1  # -1 = not started
    total_stages: int = len(STAGE_ORDER)  # 5
    stage_detail: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    use_llm: bool = False
    log: deque = field(default_factory=lambda: deque(maxlen=200))

    def to_dict(self) -> dict:
        """Convert the job state to a plain dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "current_stage": self.current_stage,
            "stage_index": self.stage_index,
            "total_stages": self.total_stages,
            "stage_detail": self.stage_detail,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "use_llm": self.use_llm,
            "log": list(self.log),
        }


class CrawlManager:
    """Manages background crawl pipeline execution.

    Usage::

        manager = CrawlManager(config_path="config/config.yaml")
        manager.set_on_complete(my_reload_callback)
        result = manager.start(use_llm=False)
        status = manager.get_status()
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self.job: CrawlJob = CrawlJob(job_id="none")
        self._on_complete_callback: Callable | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def set_on_complete(self, callback: Callable) -> None:
        """Register a callback invoked after a successful crawl.

        Typically used to trigger a knowledge-base reload in the server.
        """
        self._on_complete_callback = callback

    def is_running(self) -> bool:
        """Return True if a pipeline is currently executing.

        Also recovers from stale "running" state if the thread has died.
        """
        if self.job.status == "running":
            # Check if thread is actually alive; recover if it crashed
            if self._thread is None or not self._thread.is_alive():
                self.job.status = "failed"
                self.job.current_stage = CrawlStage.FAILED.value
                self.job.error = self.job.error or "Pipeline thread died unexpectedly"
                self.job.completed_at = datetime.utcnow().isoformat()
                self._log("Recovered from stale running state (thread dead)")
                return False
            return True
        return False

    def get_status(self) -> dict:
        """Return the current job state as a plain dict."""
        return self.job.to_dict()

    def start(self, use_llm: bool = False) -> dict:
        """Kick off a new crawl pipeline in a background thread.

        Returns an error dict if a crawl is already running, otherwise
        returns the initial job state.
        """
        with self._lock:
            if self.is_running():
                return {
                    "error": "A crawl is already running",
                    "job": self.job.to_dict(),
                }

            job_id = uuid.uuid4().hex[:12]
            self.job = CrawlJob(
                job_id=job_id,
                status="running",
                started_at=datetime.utcnow().isoformat(),
                use_llm=use_llm,
            )

        self._thread = threading.Thread(
            target=self._run_pipeline,
            name=f"crawl-{job_id}",
            daemon=True,
        )
        self._thread.start()

        return self.job.to_dict()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        """Append a timestamped message to the job log."""
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        self.job.log.append(f"[{timestamp}] {message}")

    def _set_stage(self, stage: CrawlStage, detail: str = "") -> None:
        """Advance the job to *stage* and update related fields."""
        self.job.current_stage = stage.value
        if stage in STAGE_ORDER:
            self.job.stage_index = STAGE_ORDER.index(stage)
        self.job.stage_detail = detail
        self._log(f"Stage: {stage.value}" + (f" - {detail}" if detail else ""))

    def _run_pipeline(self) -> None:
        """Execute the full crawl pipeline (runs in a daemon thread)."""
        try:
            # Import pipeline functions here to avoid circular imports
            # (server.py imports this module, and main.py imports shared deps).
            from ..main import load_config, run_crawl, run_clone, run_analyze, run_generate, discover_local_repos, _get_platform

            # ---- Load config ----
            self._log(f"Loading config from {self.config_path}")
            config = load_config(Path(self.config_path))
            platform = _get_platform(config)

            repo_paths = []

            if platform == "local":
                # ---- Local-only: scan directories ----
                self._set_stage(CrawlStage.DISCOVER, "Scanning local directories")
                repo_paths = discover_local_repos(config)
                self._log(f"Found {len(repo_paths)} local repositories")

                # Skip clone stage for local repos
                self._set_stage(CrawlStage.CLONE, "Skipped (local repos)")
                self._log("Clone stage skipped for local directories")
            else:
                # ---- DISCOVER ----
                self._set_stage(CrawlStage.DISCOVER, "Discovering repositories")
                repos = run_crawl(config)
                self._log(f"Discovered {len(repos)} repositories")

                # Also scan local directories if configured alongside the API platform
                if "local" in config:
                    local_paths = discover_local_repos(config)
                    self._log(f"Also found {len(local_paths)} local repositories")
                else:
                    local_paths = []

                # ---- CLONE ----
                self._set_stage(CrawlStage.CLONE, "Cloning repositories")
                repo_paths = run_clone(config, repos)
                self._log(f"Cloned {len(repo_paths)} repositories successfully")

                # Merge local paths into the set
                repo_paths.extend(local_paths)

            # ---- ANALYZE ----
            mode = "LLM" if self.job.use_llm else "pattern"
            self._set_stage(CrawlStage.ANALYZE, f"Analyzing with {mode} extraction")
            kb = run_analyze(config, repo_paths, use_llm=self.job.use_llm)
            summary = kb.get_summary()
            self._log(
                f"Analysis complete: "
                f"{summary['repositories_analyzed']} repos, "
                f"{summary['total_schemas']} schemas, "
                f"{summary['total_apis']} APIs, "
                f"{summary['total_services']} services, "
                f"{summary['total_dependencies']} dependencies"
            )

            # ---- OUTPUT ----
            self._set_stage(CrawlStage.OUTPUT, "Generating output files")
            run_generate(config, kb)
            self._log("Output generation complete")

            # ---- RELOADING ----
            self._set_stage(CrawlStage.RELOADING, "Reloading knowledge base")
            if self._on_complete_callback:
                self._on_complete_callback()
                self._log("Knowledge base reloaded")
            else:
                self._log("No reload callback registered, skipping")

            # ---- COMPLETED ----
            self.job.status = "completed"
            self.job.current_stage = CrawlStage.COMPLETED.value
            self.job.completed_at = datetime.utcnow().isoformat()
            self._log("Crawl pipeline finished successfully")

        except Exception as exc:
            self.job.status = "failed"
            self.job.current_stage = CrawlStage.FAILED.value
            self.job.error = str(exc)
            self.job.completed_at = datetime.utcnow().isoformat()
            self._log(f"Pipeline failed: {exc}")
