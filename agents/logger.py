"""
Centralized logging for the agent pipeline.

Three sinks:
  1. Console -- colored, human-readable, for the developer
  2. File    -- /tmp/ms_prototype.log, full debug trail
  3. Memory  -- last N records, displayed in the Streamlit UI

In a regulated firm, an audit trail of every agent action and every LLM call
is non-negotiable. This module is what the prototype uses to demonstrate that.
"""
import logging
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, List, Optional


# ---------------------------------------------------------------------------
# ANSI colors for console
# ---------------------------------------------------------------------------
class _Colors:
    GREY = "\033[90m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


_LEVEL_COLORS = {
    "DEBUG": _Colors.GREY,
    "INFO": _Colors.CYAN,
    "WARNING": _Colors.YELLOW,
    "ERROR": _Colors.RED,
    "CRITICAL": _Colors.RED + _Colors.BOLD,
}


# ---------------------------------------------------------------------------
# In-memory buffer (also used by the UI)
# ---------------------------------------------------------------------------
_MEMORY_BUFFER: Deque[Dict] = deque(maxlen=500)


def get_memory_log() -> List[Dict]:
    """Returns a snapshot of the in-memory log buffer (newest last)."""
    return list(_MEMORY_BUFFER)


def clear_memory_log() -> None:
    _MEMORY_BUFFER.clear()


# ---------------------------------------------------------------------------
# Custom handler that writes to memory
# ---------------------------------------------------------------------------
class _MemoryHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _MEMORY_BUFFER.append({
            "ts": datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3],
            "level": record.levelname,
            "agent": getattr(record, "agent", record.name),
            "message": record.getMessage(),
            "extras": getattr(record, "extras", {}),
        })


class _ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        agent = getattr(record, "agent", record.name)
        prefix = f"{_Colors.GREY}{ts}{_Colors.RESET} {color}{record.levelname:<7}{_Colors.RESET} {_Colors.BLUE}[{agent}]{_Colors.RESET}"
        message = record.getMessage()
        extras = getattr(record, "extras", None)
        if extras:
            extra_str = " ".join(f"{_Colors.GREY}{k}={_Colors.RESET}{v}" for k, v in extras.items())
            return f"{prefix} {message}  {extra_str}"
        return f"{prefix} {message}"


# ---------------------------------------------------------------------------
# Setup (idempotent)
# ---------------------------------------------------------------------------
_INITIALIZED = False
LOG_FILE = Path("/tmp/ms_prototype.log")


def _init():
    global _INITIALIZED
    if _INITIALIZED:
        return
    root = logging.getLogger("ms")
    root.setLevel(logging.DEBUG)
    root.propagate = False

    # Console
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(_ConsoleFormatter())
    root.addHandler(console)

    # File
    try:
        file_h = logging.FileHandler(LOG_FILE, mode="a")
        file_h.setLevel(logging.DEBUG)
        file_h.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s"
        ))
        root.addHandler(file_h)
    except Exception:
        # File logging is best-effort -- don't crash if /tmp is read-only
        pass

    # Memory
    mem = _MemoryHandler()
    mem.setLevel(logging.DEBUG)
    root.addHandler(mem)

    _INITIALIZED = True


def get_logger(agent_name: str) -> "AgentLogger":
    _init()
    return AgentLogger(agent_name)


# ---------------------------------------------------------------------------
# Wrapper that injects the agent name and supports `extras` cleanly
# ---------------------------------------------------------------------------
class AgentLogger:
    def __init__(self, agent_name: str):
        self.agent = agent_name
        self._logger = logging.getLogger(f"ms.{agent_name}")

    def _log(self, level: int, message: str, **extras):
        self._logger.log(
            level,
            message,
            extra={"agent": self.agent, "extras": extras},
        )

    def debug(self, message: str, **extras):    self._log(logging.DEBUG, message, **extras)
    def info(self, message: str, **extras):     self._log(logging.INFO, message, **extras)
    def warning(self, message: str, **extras):  self._log(logging.WARNING, message, **extras)
    def error(self, message: str, **extras):    self._log(logging.ERROR, message, **extras)
    def critical(self, message: str, **extras): self._log(logging.CRITICAL, message, **extras)

    # Convenience: time a block
    def timed(self, message: str):
        return _Timer(self, message)


class _Timer:
    """Context manager for `with logger.timed("doing X"):`"""
    def __init__(self, logger: AgentLogger, message: str):
        self.logger = logger
        self.message = message
        self.start = 0.0

    def __enter__(self):
        self.start = time.time()
        self.logger.info(f"▶ {self.message}")
        return self

    def __exit__(self, exc_type, exc, tb):
        elapsed = time.time() - self.start
        if exc:
            self.logger.error(f"✗ {self.message} failed after {elapsed*1000:.0f}ms", error=str(exc))
        else:
            self.logger.info(f"✓ {self.message}", elapsed_ms=f"{elapsed*1000:.0f}")
