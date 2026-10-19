"""Build the URL an app puts in its signing iframe."""

from __future__ import annotations

import base64
import json
from urllib.parse import quote


def build_embed_url(
    base_url: str,
    signing_token: str,
    *,
    name: str | None = None,
    email: str | None = None,
    lock_identity: bool = True,
    language: str | None = None,
    dark_mode_disabled: bool = True,
    allow_rejection: bool = False,
) -> str:
    """`{base}/embed/sign/{token}#{options}`.

    Documenso reads the options from the hash as
    btoa(encodeURIComponent(JSON.stringify(options))); the hash never reaches
    the server. `lock_identity` pins the name/email the app already knows.
    """
    options: dict = {
        "darkModeDisabled": dark_mode_disabled,
        "allowDocumentRejection": allow_rejection,
    }
    if name:
        options["name"] = name
        options["lockName"] = lock_identity
    if email:
        options["email"] = email
        options["lockEmail"] = lock_identity
    if language:
        options["language"] = language
    encoded = base64.b64encode(quote(json.dumps(options), safe="").encode()).decode()
    return f"{base_url.rstrip('/')}/embed/sign/{signing_token}#{encoded}"
