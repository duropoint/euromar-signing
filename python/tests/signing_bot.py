"""Drives Documenso's embedded signing UI headlessly, the way a person would,
from inside a host page that iframes the embed URL (like an app does).

Test-only. Selectors follow Documenso's own e2e suite (signature-pad test ids,
"Next Field" / "Complete" / "Sign" buttons) for the pinned version. Fields on
the v2 PDF viewer are canvas-drawn (no DOM node), so each one is clicked just
below the "Click to insert field" tooltip that "Next Field" shows above it.
"""

from __future__ import annotations

import http.server
import os
import socketserver
import tempfile
import threading
from contextlib import contextmanager

CHROMIUM = os.environ.get("CHROMIUM_PATH") or None
if CHROMIUM is None and os.path.exists("/opt/pw-browsers/chromium"):
    CHROMIUM = "/opt/pw-browsers/chromium"

HOST_PAGE = """<!doctype html><html><body style="margin:0">
<iframe id="signing" src="{url}" style="width:1200px;height:1500px;border:0"></iframe>
<script>
  window.messages = [];
  addEventListener("message", (e) => window.messages.push({{origin: e.origin, data: e.data}}));
</script></body></html>"""


@contextmanager
def _serve_host_page(embed_url: str):
    # Served from localhost (not a mocked origin): Chromium's private-network
    # rules block a "public" page from framing a localhost Documenso.
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "index.html"), "w") as fh:
            fh.write(HOST_PAGE.format(url=embed_url))

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=root, **kw)

            def log_message(self, *a):
                pass

        with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                yield f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
            finally:
                httpd.shutdown()


def sign_in_embed(
    embed_url: str, *, typed_signature: str = "Test Signer", max_fields: int = 20
) -> list[dict]:
    """Type a signature once, insert it into every field, complete. Returns
    the postMessage events the host page received."""
    from playwright.sync_api import sync_playwright

    with _serve_host_page(embed_url) as host_url, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 1600})
            page.goto(host_url)
            frame = page.frame_locator("#signing")
            page.wait_for_function(
                "window.messages.some(m => m.data && m.data.action === 'document-ready')",
                timeout=60_000,
            )

            frame.get_by_test_id("signature-pad-dialog-button").first.click()
            frame.get_by_role("tab", name="Type").click()
            frame.get_by_test_id("signature-pad-type-input").fill(typed_signature)
            frame.get_by_role("button", name="Next").click()
            page.wait_for_timeout(500)

            complete = frame.get_by_role("button", name="Complete")
            for _ in range(max_fields):
                if complete.count():
                    break
                frame.get_by_role("button", name="Next Field").first.click()
                tip = frame.get_by_text("Click to insert field").first
                tip.wait_for(timeout=10_000)
                bb = tip.bounding_box()
                page.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] + 20)
                page.wait_for_timeout(800)

            complete.first.click()
            frame.get_by_role("dialog").get_by_role("button", name="Sign").click()
            page.wait_for_function(
                "window.messages.some(m => m.data && m.data.action === 'document-completed')",
                timeout=60_000,
            )
            return page.evaluate("window.messages")
        finally:
            browser.close()
