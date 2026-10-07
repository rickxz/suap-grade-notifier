from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .client import Session
from .model import Snapshot

log = logging.getLogger(__name__)


def data_dir() -> Path:
    override = os.environ.get("SUAP_NOTIFIER_HOME")
    if override:
        base = Path(override)
    elif os.name == "nt":
        base = Path(os.environ["LOCALAPPDATA"]) / "suap-notifier"
    else:
        base = Path.home() / ".local" / "share" / "suap-notifier"
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class State:
    session: Session | None = None
    snapshot: Snapshot | None = None
    # Last failure we already toasted about, so a broken login doesn't notify every 30 minutes
    alerted: str | None = None
    consecutive_failures: int = 0

    @classmethod
    def load(cls) -> State:
        path = data_dir() / "state.json"
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            snapshot = Snapshot.from_dict(raw["snapshot"]) if raw.get("snapshot") is not None else None
            session = Session(**raw["session"]) if raw.get("session") else None
            return cls(
                session=session,
                snapshot=snapshot,
                alerted=raw.get("alerted"),
                consecutive_failures=raw.get("consecutive_failures", 0),
            )
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            # Starting over only costs a silent new baseline; crashing would stop every future run
            corrupt = path.with_suffix(".corrupt.json")
            log.warning("unreadable state file (%s), moved to %s", exc, corrupt.name)
            path.replace(corrupt)
            return cls()

    def save(self) -> None:
        path = data_dir() / "state.json"
        payload = {
            "session": asdict(self.session) if self.session else None,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "alerted": self.alerted,
            "consecutive_failures": self.consecutive_failures,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
