from __future__ import annotations

from dataclasses import dataclass

import httpx

from .model import Snapshot
from .parse import parse_boletim, parse_detail

DOMAIN = "suap.ifsp.edu.br"
BASE_URL = f"https://{DOMAIN}"
LOGIN_PATH = "/accounts/login/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"


@dataclass
class Session:
    # SUAP ties the session to its `_did` device cookie: replaying sessionid without it logs the user out
    cookies: dict[str, str]
    user_agent: str = USER_AGENT


class SessionExpired(Exception):
    pass


class SuapUnavailable(Exception):
    pass


def boletim_url(prontuario: str) -> str:
    return f"{BASE_URL}/edu/aluno/{prontuario.upper()}/?tab=boletim"


class SuapClient:
    def __init__(self, session: Session, transport: httpx.BaseTransport | None = None):
        self.user_agent = session.user_agent
        cookies = httpx.Cookies()
        # Same domain/path as SUAP's Set-Cookie, so re-signed cookies replace these instead of duplicating them
        for name, value in session.cookies.items():
            cookies.set(name, value, domain=DOMAIN, path="/")
        self.http = httpx.Client(
            base_url=BASE_URL,
            cookies=cookies,
            follow_redirects=False,
            timeout=30,
            headers={"User-Agent": session.user_agent},
            transport=transport,
        )

    def __enter__(self) -> SuapClient:
        return self

    def __exit__(self, *exc) -> None:
        self.http.close()

    @property
    def session(self) -> Session:
        # SUAP re-signs `_did` on every response, so the latest cookies must be persisted
        return Session({cookie.name: cookie.value for cookie in self.http.cookies.jar}, self.user_agent)

    def fetch_snapshot(self, prontuario: str) -> Snapshot:
        # Partial data is never returned: saving it would make the next full fetch re-report every grade
        subjects = parse_boletim(self._get(f"/edu/aluno/{prontuario.upper()}/boletins/"))
        if subjects is None:
            raise SuapUnavailable("boletim table not found")
        for subject in subjects:
            if not subject.detail_url:
                continue
            assessments = parse_detail(self._get_detail(subject.detail_url))
            if assessments is None:
                raise SuapUnavailable(f"grade details not found at {subject.detail_url}")
            subject.assessments = assessments
        return Snapshot({subject.diario: subject for subject in subjects})

    def _get_detail(self, path: str) -> str:
        try:
            return self._get(path)
        except SessionExpired:
            # The boletim was just served with this session, so a 403 here is about this page, not the login
            raise SuapUnavailable(f"detail page refused with a valid session: {path}") from None

    def _get(self, path: str) -> str:
        try:
            response = self.http.get(path)
        except httpx.HTTPError as exc:
            raise SuapUnavailable(str(exc)) from exc

        # Logged-in pages never redirect: without a session SUAP sends the boletim to "/" (not the
        # login page) and answers 403 on detail pages
        if response.is_redirect or response.status_code in (401, 403):
            raise SessionExpired
        if not response.is_success:
            raise SuapUnavailable(f"GET {path} -> {response.status_code}")
        return response.text
