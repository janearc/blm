# birblib

The birb archetype layer on top of Big Little Mesh's `frood`. A birb is mostly *declaration*
and almost no orchestration: it declares its kind, its banchans, and its recipe, and
implements one method — `cook()`. birblib provides the rest.

birblib depends on `frood` (the bus/mesh frood layer, generic to all pipelines)
and knows nothing birb-specific. See `design-docs/blm-substrate-contracts-design.md` in
`archaea` for the full rationale; this README is the usage view.

## The shape of a birb

```python
from pathlib import Path
from birblib import BirbBento, BirbHandlers, CookResult, Stage, driver

DATA_ROOT = Path.home() / "var" / "mybirb" / "bentos"


class MyBirb(BirbHandlers):
    kind = "audio.ingest"          # namespaced
    source_banchan = "audio"       # the input to dup in at NOTICED (None for prompt-only birbs)
    artifact_banchan = "transcript"  # the primary output cook() produces

    def cook(self, b) -> CookResult:
        bento = BirbBento(b)
        with Stage("transcribe", self.stats):     # times the sub-stage into the manifest
            text = transcribe(bento.banchan("audio").location)
        out = bento.out_dir / "transcript.txt"
        out.write_text(text)
        return CookResult(artifact=str(out), ok=True, detail={})


def process(audio_path: Path) -> dict:
    bento = BirbBento.new(
        kind=MyBirb.kind, bentos_root=DATA_ROOT, name=audio_path.name,
        banchans=[("audio", "source", audio_path)],
    )
    return driver.run(MyBirb(), bento)   # raises if the bento ends FAILED
```

`BirbHandlers` drives `NOTICED → COOK → (DONE | PARTIAL → DONE | FAILED)`:

- **`on_noticed`** scaffolds the bento, copies the source in (dup-over-loss — never moves
  the operator's original), repoints the source banchan, and persists the bento to
  `root/bento.json` (the on-disk SOT). A missing source ⇒ FAILED.
- **`on_cook`** calls your `cook()`. A raised exception ⇒ FAILED (and `driver.run` raises);
  `ok=False` ⇒ PARTIAL (degraded-but-usable); `ok=True` ⇒ DONE. It records the artifact
  banchan and writes the manifest.
- **`on_partial`** is the convergence seam. Default: accept the degraded artifact and
  finish DONE (raw beats nothing). Override when substrate convergence is defined.

## The manifest envelope

`driver.run` returns a typed `birblib.Manifest` (a frozen dataclass — the manifest is a
*derived view* that crosses the disk + HTTP/CLI edge, not a wire contract; `bento.proto`
stays the wire SOT). `BirbBento.write_manifest` serializes `.to_dict()` to
`root/manifest.json`; `Manifest.from_dict` parses it back (the boundary is typed on read,
too):

```json
{
  "bento_id": "…", "kind": "audio.ingest",
  "ok": true, "state": "DONE",
  "artifact": "/…/outputs/transcript.txt",
  "params": { … }, "stats": { "transcribe": { "wall_s": 4.1, "cpu_s": 0.2 } },
  "detail": { … }
}
```

`ok` (`state == DONE`) is the single success signal. `params` is the resolved request a
birb archives at NOTICED (declare it via `BirbHandlers.request()` — default is the bento's
prompt — and it lands in `raw_data/request.json` so a replay can reconstruct intent).
`detail` is pipeline-specific and namespaced — degrade reasons, the dispatcher's decision
tree, never spread at top level.

## The other seams

- **`birblib.dispatch`** — the gated-backend seam. `Backend` protocol (`name`,
  `available() -> (ok, reason)`, `run(...)`) + `dispatch(backends, *args, prefer=None)`:
  probes in order, runs the first usable, falls through on a runtime failure (never
  fabricates), returns `(output, detail)` with the full decision tree. Raises
  `NoBackendAvailable(detail)` when nothing is usable — the caller decides degrade vs fail.
- **`birblib.recipe`** — `Request` + `resolve(recipe_values, overrides, overridable)`:
  lay caller overrides over the pipeline's tuned values, reject unknown keys, record
  overriding as the `anti_pattern` signal. (Recipe scope is open decision §9.2.)
- **`birblib.service`** — `serve_inbox(provider, …)` drives a `frood` watcher over a
  [Provider](../../docs/providers.md) (intake, the persistent restart-surviving dedup, the
  partial-write guard, and the terminal notify are the provider's job) with the real sidecar
  emit; `build_app(...)` is the `/health`, `202`-submit + `GET /jobs/{id}` poll, and
  `/artifacts/{id}/{name}` traversal-guarded surface; `ack(...)` is the JSON-by-default CLI
  ACK. The HTTP half needs the optional extra: `pip install big-little-mesh-frood[service]`.
  **`build_app`'s `POST /jobs` is a single-node/local-dev affordance** — it persists the
  NOTICED bento then drives it on an in-process thread; the *fleet* submit path is bus-enqueue
  (persist, emit NOTICED, let a bus worker drive it). The per-modality `/v1` facade stays the
  birb's own.
- **`birblib.lang`** — ISO 639-1 as the canonical language id, `display_name(code)` for a
  human-readable name in a prompt (fails loud on an unknown code; never passes a bare code
  through — the `"fluent en"` bug).
- **`birblib.names.safe_name`** — the filename normalizer the file-ingest birbs all carried.

## See also

- [docs/states.md](../../docs/states.md) — the lifecycle and each handler's MUST/MAY (RFC 2119).
- [docs/providers.md](../../docs/providers.md) — the I/O seam (`read`/`write`/`notify`).
- [docs/pipelines.md](../../docs/pipelines.md) — bento/banchan and the project ⊇ pipeline ⊇ birb taxonomy.
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — version discipline and the freeze/seam boundary.

## Open decisions (track in the PR, not frozen here)

1. **Lib name/home** (§9.1): `birblib` ships in the `big-little-mesh-frood` distribution as a
   distinct top-level package, to keep cross-repo installs to one git dependency on a
   connectivity-hostile network. A separate `big-little-mesh-birblib` distribution is a mechanical move.
2. **Recipe scope** (§9.2): leaf-birbs-only vs substrate-wide. `birblib.recipe` is the
   minimal override-recording seam; the `params` shape is not frozen.
3. **PARTIAL / convergence** (§9.3): `on_partial → DONE` is the documented stopgap.
4. **Bus-as-SOT vs on-disk bento** (§9.4): birblib persists `bento.json` for the local path.
