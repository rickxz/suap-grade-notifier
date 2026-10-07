import pytest

from suap_notifier import app
from suap_notifier.auth import LoginFailed
from suap_notifier.client import Session, SessionExpired, SuapUnavailable
from suap_notifier.model import Assessment, Snapshot, Subject
from suap_notifier.parse import LayoutChanged
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


def test_layout_change_alerts_once_and_keeps_the_snapshot(env, monkeypatch):
    save_state(session=Session({"sessionid": "a"}), snapshot=snapshot("8,00"))

    def fetch(state, creds):
        raise LayoutChanged("no DISCIPLINA column")

    monkeypatch.setattr(app, "fetch", fetch)

    app.run()
    app.run()

    assert [title for title, _ in env] == ["O SUAP mudou a página do boletim"]
    assert State.load().snapshot == snapshot("8,00")


def test_unexpected_failure_alerts_once_and_still_fails(env, monkeypatch):
    def fetch(state, creds):
        raise KeyError("Disciplina")

    monkeypatch.setattr(app, "fetch", fetch)

    for _ in range(2):
        with pytest.raises(KeyError):
            app.run()

    assert [title for title, _ in env] == ["SUAP Notifier parou de funcionar"]


def test_expired_session_redirecting_home_triggers_a_new_login(env, monkeypatch):
    save_state(session=Session({"sessionid": "old"}), snapshot=snapshot("8,00"))
    logins = []

    def browser_login(*args, **kwargs):
        logins.append(args)
        return Session({"sessionid": "fresh"})

    def fetch_with_session(state, creds):
        if state.session.cookies["sessionid"] == "old":
            raise SessionExpired
        return snapshot("8,00")

    monkeypatch.setattr(app, "browser_login", browser_login)
    monkeypatch.setattr(app, "_fetch_with_session", fetch_with_session)

    app.run()

    assert len(logins) == 1
    assert State.load().session.cookies == {"sessionid": "fresh"}


def test_repeated_unavailability_alerts_once_after_the_threshold(env, monkeypatch):
    save_state(session=Session({"sessionid": "a"}), snapshot=snapshot(None))

    def fetch(state, creds):
        raise SuapUnavailable("GET /boletins/ -> 502")

    monkeypatch.setattr(app, "fetch", fetch)

    for _ in range(app.FAILURES_BEFORE_ALERT - 1):
        app.run()
    assert env == []

    app.run()
    app.run()

    assert [title for title, _ in env] == ["SUAP Notifier não está conseguindo verificar o boletim"]


def test_success_resets_the_failure_count(env, monkeypatch):
    save_state(session=Session({"sessionid": "a"}), snapshot=snapshot(None), consecutive_failures=2, alerted="unavailable")
    monkeypatch.setattr(app, "fetch", lambda state, creds: snapshot(None))

    app.run()

    saved = State.load()
    assert (saved.consecutive_failures, saved.alerted) == (0, None)
