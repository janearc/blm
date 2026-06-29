# frood model client (Python half), mirroring the Go client.
#
# resolve a logical model name to a backend via delightd's discovery, fail-closed,
# and invoke it by provider. paling/magpie daemons use this; crepe/delightd use the
# Go client; both over the same model.v1 contract. Generalized from paling's
# modelclient -- stdlib only, no deps, so any Python frood can import it.
#
# fail-closed is deliberate (the availability mandate): if delightd is down or nothing
# healthy serves the model, raise ModelUnavailable rather than inventing a local
# fallback. Resilience lives in delightd coming up, not in each consumer hedging.

import json
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_DELIGHTD_URL = os.environ.get("DELIGHTD_URL", "http://localhost:8088")


class ModelUnavailable(RuntimeError):  # noqa: N818 - public name, matches the Go ErrModelUnavailable
    # no healthy backend could be resolved for the requested model.
    pass


def resolve(name, delightd_url=None, timeout=3):
    # resolve a logical model name to {provider, url, model} via delightd. Returns the
    # first healthy provider whose served model name contains `name` (ollama reports
    # e.g. "mistral:latest", so we substring-match), or None if delightd is unreachable
    # or nothing healthy serves it -- fail-closed.
    base = (delightd_url or DEFAULT_DELIGHTD_URL).rstrip("/")
    try:
        with urllib.request.urlopen(base + "/discovery/llms", timeout=timeout) as r:
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001 - any failure is "unavailable", logged
        logger.warning("delightd discovery unreachable (%s): %s", base, e)
        return None

    want = name.lower()
    for src in data.get("sources", []):
        if not src.get("healthy"):
            continue
        for m in src.get("models", []):
            if want in m.lower():
                return {"provider": src.get("provider"), "url": src.get("url"), "model": m}
    logger.warning("no healthy provider serves model %r", name)
    return None


def generate(name, prompt, delightd_url=None, timeout=120, **opts):
    # resolve `name` and run a single (non-streaming) completion, by provider. Raises
    # ModelUnavailable if nothing serves the model (fail-closed). Only the ollama
    # provider is wired here; in-process (MLX/transformers) and remote providers land
    # with the in-process backend and the model-svc gateway.
    backend = resolve(name, delightd_url=delightd_url)
    if backend is None:
        raise ModelUnavailable(f"no backend serves model {name!r} (is delightd up?)")

    provider = (backend.get("provider") or "").lower()
    if provider != "ollama":
        raise NotImplementedError(f"provider {provider!r} not yet supported by the Python client")

    payload = {"model": backend["model"], "prompt": prompt, "stream": False}
    payload.update(opts)
    req = urllib.request.Request(
        backend["url"].rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("response", "")
