import pytest

from suap_notifier import app
from suap_notifier.auth import LoginFailed
from suap_notifier.client import Session, SessionExpired, SuapUnavailable
from suap_notifier.model import Assessment, Snapshot, Subject
from suap_notifier.state import State, data_dir


def snapshot(nota):
    a1 = Assessment("Etapa 1", "A1", "Prova", None, None, None, nota)
    return Snapshot({"1": Subject("1", "Cálculo II", "Cursando", 0, "100%", {"N1": None}, None, {a1.key: a1})})


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SUAP_NOTIFIER_HOME", str(tmp_path))
    monkeypatch.setattr(app.Credentials, "load", classmethod(lambda cls: cls("SC0000000", "secret")))
    shown = []
    monkeypatch.setattr(app.notify, "show", lambda title, lines, url=None: shown.append((title, lines)) or True)
    return shown


def save_state(**kwargs):
    State(**kwargs).save()


def test_first_run_saves_baseline_without_notifying(env, monkeypatch):
    monkeypatch.setattr(app, "fetch", lambda state, creds: snapshot(None))

    app.run()

    assert env == []
    assert State.load().snapshot == snapshot(None)


def test_change_is_notified_and_saved(env, monkeypatch):
    save_state(session=Session({"sessionid": "a"}), snapshot=snapshot(None))
    monkeypatch.setattr(app, "fetch", lambda state, creds: snapshot("8,00"))

    app.run()

    assert env == [("SUAP: 1 atualização no boletim", ["Cálculo II · A1 (Etapa 1): 8,00"])]
    assert State.load().snapshot == snapshot("8,00")


def test_failed_notification_keeps_previous_snapshot_for_retry(env, monkeypatch):
    save_state(session=Session({"sessionid": "a"}), snapshot=snapshot(None))
    monkeypatch.setattr(app, "fetch", lambda state, creds: snapshot("8,00"))
    monkeypatch.setattr(app.notify, "show", lambda *a, **k: False)

    app.run()

    assert State.load().snapshot == snapshot(None)


def test_unavailable_suap_still_persists_a_fresh_session(env, monkeypatch):
    save_state(session=Session({"sessionid": "old"}), snapshot=snapshot(None))

    def fetch(state, creds):
        state.session = Session({"sessionid": "new"})
        raise SuapUnavailable("detail timed out")

    monkeypatch.setattr(app, "fetch", fetch)

    app.run()

    saved = State.load()
    assert saved.session.cookies == {"sessionid": "new"}
    assert saved.snapshot == snapshot(None)
    assert env == []


def test_login_failure_alerts_only_once(env, monkeypatch):
    def fetch(state, creds):
        raise LoginFailed("captcha")

    monkeypatch.setattr(app, "fetch", fetch)

    app.run()
    app.run()

    assert [title for title, _ in env] == ["Não foi possível entrar no SUAP automaticamente"]


def test_session_rejected_right_after_login_is_a_login_failure(env, monkeypatch):
    def always_expired(state, creds):
        raise SessionExpired

    monkeypatch.setattr(app, "_fetch_with_session", always_expired)
    monkeypatch.setattr(app, "browser_login", lambda *a, **k: Session({"sessionid": "fresh"}))

    with pytest.raises(LoginFailed):
        app.fetch(State(session=Session({"sessionid": "stale"})), app.Credentials("SC0000000", "secret"))


def test_corrupt_state_file_starts_over(env):
    (data_dir() / "state.json").write_text("{not json", encoding="utf-8")

    assert State.load() == State()
    assert (data_dir() / "state.corrupt.json").exists()
