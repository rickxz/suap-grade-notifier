from __future__ import annotations

import logging
from dataclasses import dataclass

import keyring

from . import notify
from .auth import BadCredentials, LoginFailed, browser_login
from .client import SessionExpired, SuapClient, SuapUnavailable, boletim_url
from .model import Snapshot, diff
from .state import State

log = logging.getLogger(__name__)

KEYRING_SERVICE = "suap-notifier"
KEYRING_USER_ENTRY = "prontuario"


@dataclass
class Credentials:
    prontuario: str
    password: str

    @classmethod
    def load(cls) -> Credentials | None:
        prontuario = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_ENTRY)
        if not prontuario:
            return None
        password = keyring.get_password(KEYRING_SERVICE, prontuario)
        return cls(prontuario, password) if password else None

    def save(self) -> None:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER_ENTRY, self.prontuario)
        keyring.set_password(KEYRING_SERVICE, self.prontuario, self.password)

    @staticmethod
    def stored_prontuario() -> str | None:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER_ENTRY)

    @staticmethod
    def forget() -> None:
        prontuario = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_ENTRY)
        for entry in (prontuario, KEYRING_USER_ENTRY):
            if entry and keyring.get_password(KEYRING_SERVICE, entry) is not None:
                keyring.delete_password(KEYRING_SERVICE, entry)


def fetch(state: State, creds: Credentials) -> Snapshot:
    if state.session is None:
        state.session = browser_login(creds.prontuario, creds.password)
    try:
        return _fetch_with_session(state, creds)
    except SessionExpired:
        log.info("session expired, logging in again")
        state.session = browser_login(creds.prontuario, creds.password)
    try:
        return _fetch_with_session(state, creds)
    except SessionExpired:
        raise LoginFailed("SUAP rejected the session right after logging in") from None


def _fetch_with_session(state: State, creds: Credentials) -> Snapshot:
    with SuapClient(state.session) as client:
        try:
            return client.fetch_snapshot(creds.prontuario)
        finally:
            state.session = client.session


def run() -> None:
    state = State.load()
    try:
        _check(state)
    finally:
        # Even failed runs may have logged in again or received re-signed cookies worth keeping
        state.save()


def _check(state: State) -> None:
    creds = Credentials.load()
    if creds is None:
        _alert_once(state, "no-credentials", "SUAP Notifier não configurado", ["Rode: python -m suap_notifier setup"])
        return

    try:
        snapshot = fetch(state, creds)
    except BadCredentials:
        log.error("SUAP rejected the stored password")
        _alert_once(state, "bad-credentials", "Login no SUAP falhou", ["A senha salva foi recusada. Rode o setup novamente."])
        return
    except LoginFailed as exc:
        log.error("automatic login failed: %s", exc)
        _alert_once(
            state,
            "login-failed",
            "Não foi possível entrar no SUAP automaticamente",
            ["Rode: python -m suap_notifier login"],
        )
        return
    except SuapUnavailable as exc:
        log.warning("SUAP unavailable: %s", exc)
        return

    state.alerted = None
    if state.snapshot is None:
        log.info("baseline saved with %d subjects", len(snapshot.subjects))
        state.snapshot = snapshot
        return

    changes = diff(state.snapshot, snapshot)
    log.info("%d change(s) found", len(changes))
    if not changes:
        state.snapshot = snapshot
        return

    title = "SUAP: 1 atualização no boletim" if len(changes) == 1 else f"SUAP: {len(changes)} atualizações no boletim"
    if not notify.show(title, [change.describe() for change in changes], boletim_url(creds.prontuario)):
        log.warning("notification failed, keeping the previous snapshot so these changes are reported next run")
        return
    state.snapshot = snapshot


def dry_run() -> Snapshot:
    state = State.load()
    creds = Credentials.load()
    if creds is None:
        raise SystemExit("Sem credenciais salvas. Rode: python -m suap_notifier setup")
    snapshot = fetch(state, creds)
    state.save()  # persists the re-signed cookies; the stored snapshot is left untouched
    return snapshot


def setup(prontuario: str, password: str) -> int:
    creds = Credentials(prontuario.strip().upper(), password)
    session = browser_login(creds.prontuario, creds.password)

    state = State.load()
    previous_prontuario = Credentials.stored_prontuario()
    if previous_prontuario and previous_prontuario != creds.prontuario:
        # Another student's grades must not be diffed against this account's
        Credentials.forget()
        state.snapshot = None
    creds.save()
    state.session, state.alerted = session, None
    snapshot = _fetch_with_session(state, creds)
    # Re-running setup (e.g. after a password change) must not swallow changes since the last run
    if state.snapshot is None:
        state.snapshot = snapshot
    state.save()
    return len(snapshot.subjects)


def interactive_login() -> None:
    creds = Credentials.load()
    if creds is None:
        raise SystemExit("Sem credenciais salvas. Rode: python -m suap_notifier setup")
    state = State.load()
    state.session = browser_login(creds.prontuario, None, interactive=True)
    state.alerted = None
    state.save()


def _alert_once(state: State, reason: str, title: str, lines: list[str]) -> None:
    if state.alerted == reason:
        return
    if notify.show(title, lines):
        state.alerted = reason
