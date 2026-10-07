from pathlib import Path

import httpx
import pytest

from suap_notifier.client import Session, SessionExpired, SuapClient, SuapUnavailable

FIXTURES = Path(__file__).parent / "fixtures"
BOLETIM = (FIXTURES / "boletim.html").read_text(encoding="utf-8")
DETALHE = (FIXTURES / "detalhe.html").read_text(encoding="utf-8")


def client_with(handler):
    return SuapClient(Session({"sessionid": "abc", "_did": "device:1"}, "Edge UA"), httpx.MockTransport(handler))


def test_fetch_snapshot_follows_every_detalhar_link():
    requested = []

    def handler(request):
        requested.append(request.url.path)
        return httpx.Response(200, text=BOLETIM if request.url.path.endswith("/boletins/") else DETALHE)

    snapshot = client_with(handler).fetch_snapshot("sc0000000")

    assert requested == [
        "/edu/aluno/SC0000000/boletins/",
        "/edu/detalhar_matricula_diario_boletim/100000/2000001/",
        "/edu/detalhar_matricula_diario_boletim/100000/2000002/",
    ]
    assert snapshot.subjects["111111"].assessments["Etapa 1|A2"].nota == "8,00"


def test_redirect_to_login_means_session_expired():
    client = client_with(lambda r: httpx.Response(302, headers={"location": "/accounts/login/?next=/edu/"}))

    with pytest.raises(SessionExpired):
        client.fetch_snapshot("SC0000000")


def test_redirect_to_home_means_session_expired():
    # What SUAP actually answers for an expired session (observed 2026-10-07)
    client = client_with(lambda r: httpx.Response(302, headers={"location": "/"}))

    with pytest.raises(SessionExpired):
        client.fetch_snapshot("SC0000000")


def test_forbidden_boletim_means_session_expired():
    client = client_with(lambda r: httpx.Response(403))

    with pytest.raises(SessionExpired):
        client.fetch_snapshot("SC0000000")


def test_forbidden_detail_after_boletim_is_not_a_session_problem():
    def handler(request):
        return httpx.Response(200, text=BOLETIM) if request.url.path.endswith("/boletins/") else httpx.Response(403)

    with pytest.raises(SuapUnavailable):
        client_with(handler).fetch_snapshot("SC0000000")


@pytest.mark.parametrize("status", [404, 429])
def test_other_client_errors_mean_unavailable(status):
    with pytest.raises(SuapUnavailable):
        client_with(lambda r: httpx.Response(status)).fetch_snapshot("SC0000000")


def test_maintenance_page_instead_of_boletim_means_unavailable():
    with pytest.raises(SuapUnavailable):
        client_with(lambda r: httpx.Response(200, text="<h1>Manutenção</h1>")).fetch_snapshot("SC0000000")


def test_maintenance_page_instead_of_detail_means_unavailable():
    def handler(request):
        return httpx.Response(200, text=BOLETIM if request.url.path.endswith("/boletins/") else "<h1>Manutenção</h1>")

    with pytest.raises(SuapUnavailable):
        client_with(handler).fetch_snapshot("SC0000000")


def test_server_error_means_unavailable():
    client = client_with(lambda r: httpx.Response(502))

    with pytest.raises(SuapUnavailable):
        client.fetch_snapshot("SC0000000")


def test_network_error_means_unavailable():
    def handler(request):
        raise httpx.ConnectError("offline")

    with pytest.raises(SuapUnavailable):
        client_with(handler).fetch_snapshot("SC0000000")


def test_sends_device_cookie_and_user_agent_and_keeps_the_resigned_one():
    seen = []

    def handler(request):
        seen.append((request.headers["cookie"], request.headers["user-agent"]))
        body = BOLETIM if request.url.path.endswith("/boletins/") else DETALHE
        return httpx.Response(200, text=body, headers={"set-cookie": "_did=device:2; Path=/; HttpOnly"})

    client = client_with(handler)
    client.fetch_snapshot("SC0000000")

    assert seen[0] == ("sessionid=abc; _did=device:1", "Edge UA")
    assert "_did=device:2" in seen[1][0] and "device:1" not in seen[1][0]
    assert client.session.cookies == {"sessionid": "abc", "_did": "device:2"}
