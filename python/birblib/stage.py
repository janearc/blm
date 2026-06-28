# birblib.stage -- Stage, a per-stage wall/cpu timer that records into a stats dict.
#
# lifted verbatim-in-behavior from the copy every audio birb carried. wall is the signal
# that matters for fan/heat: GPU work (whisper/diffusion on MLX) barely moves CPU time but
# pegs the device for the whole wall duration, so the longest-wall stage is the one cooking
# the laptop. a birb's cook() times its sub-stages with this; the stats land under the
# manifest's `stats`.

import logging
import time

logger = logging.getLogger(__name__)


class Stage:
    # time a block of work into stats[name] = {"wall_s": .., "cpu_s": ..}, and log it.
    # used as a context manager: `with Stage("transcribe", self.stats): ...`.
    def __init__(self, name: str, stats: dict) -> None:
        self.name, self.stats = name, stats

    def __enter__(self) -> "Stage":
        self._w = time.monotonic()
        self._c = time.process_time()
        return self

    def __exit__(self, *exc) -> None:
        wall = round(time.monotonic() - self._w, 2)
        cpu = round(time.process_time() - self._c, 2)
        self.stats[self.name] = {"wall_s": wall, "cpu_s": cpu}
        logger.info("stage %s: wall=%.1fs cpu=%.1fs", self.name, wall, cpu)
