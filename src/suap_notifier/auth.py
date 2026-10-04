from __future__ import annotations

import logging
import time

from .client import BASE_URL, LOGIN_PATH, Session, SuapUnavailable
from .state import data_dir

log = logging.getLogger(__name__)

LOGIN_URL = f"{BASE_URL}{LOGIN_PATH}?next=/"
WRONG_CREDENTIALS_TEXT = "usuário e senha corretos"


class BadCredentials(Exception):
    pass


class LoginFailed(Exception):
    pass


def browser_login(prontuario: str, password: str | None, interactive: bool = False) -> Session:
    """Logs in through a real Edge window and returns SUAP's cookies plus the browser's User-Agent.

    The login form is protected by reCAPTCHA v3, which only a real browser can satisfy;
    everything after login is plain HTTP using these cookies.
    """
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    # Headless Edge gets low reCAPTCHA scores, so the automatic login uses a real window parked off-screen
    args = [] if interactive else ["--window-position=-32000,-32000"]
    timeout_ms = 5 * 60_000 if interactive else 45_000

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(data_dir() / "edge-profile"),
                channel="msedge",
                headless=False,
                args=args,
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                try:
                    page.goto(LOGIN_URL)
                except PlaywrightError as exc:
                    raise SuapUnavailable(f"could not open the login page: {exc}") from exc
                if LOGIN_PATH in page.url:
                    page.fill("#id_username", prontuario)
                    if not interactive:
                        page.fill("#id_password", password or "")
                        page.click("form input[type=submit], form button[type=submit]")
                    _wait_until_logged_in(page, timeout_ms, PlaywrightError)
                cookies = {c["name"]: c["value"] for c in context.cookies(BASE_URL)}
                user_agent = page.evaluate("navigator.userAgent")
            finally:
                context.close()
    except PlaywrightError as exc:
        # Edge missing, profile locked by another run, login form changed...
        raise LoginFailed(f"browser automation failed: {exc}") from exc

    if "sessionid" not in cookies:
        raise LoginFailed("login finished without a sessionid cookie")
    log.info("browser login succeeded (interactive=%s)", interactive)
    return Session(cookies, user_agent)


def _wait_until_logged_in(page, timeout_ms: int, playwright_error: type[Exception]) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if LOGIN_PATH not in page.url:
            return
        try:
            if WRONG_CREDENTIALS_TEXT in page.content():
                raise BadCredentials
        except playwright_error:
            pass  # page.content() fails while the form submission is navigating
        page.wait_for_timeout(500)
    raise LoginFailed("SUAP kept the login page (reCAPTCHA probably rejected the attempt)")
