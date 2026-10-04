from __future__ import annotations

import base64
import logging
import os
import subprocess
from xml.sax.saxutils import escape, quoteattr

log = logging.getLogger(__name__)

POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
# PowerShell's AppUserModelID: lets an unpackaged script raise toasts without registering its own app
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
MAX_LINES = 4

TOAST_SCRIPT = """
$xml = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{payload}'))
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = New-Object Windows.UI.Notifications.ToastNotification($doc)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}').Show($toast)
"""


def show(title: str, lines: list[str], url: str | None = None) -> None:
    if len(lines) > MAX_LINES:
        lines = lines[: MAX_LINES - 1] + [f"e mais {len(lines) - MAX_LINES + 1}..."]
    body = "\n".join(lines)
    log.info("notification: %s | %s", title, body.replace("\n", " | "))

    if os.name != "nt":
        print(f"[{title}]\n{body}")
        return

    launch = f" activationType=\"protocol\" launch={quoteattr(url)}" if url else ""
    xml = (
        f"<toast duration=\"long\"{launch}><visual><binding template=\"ToastGeneric\">"
        f"<text>{escape(title)}</text><text>{escape(body)}</text>"
        "</binding></visual></toast>"
    )
    script = TOAST_SCRIPT.format(payload=base64.b64encode(xml.encode()).decode(), app_id=APP_ID)
    subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
        check=False,
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
