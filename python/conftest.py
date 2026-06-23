# put the generated gen/python tree on the path for tests, so `from bento.v1 import
# bento_pb2 / bento_fsm` resolves the same way it does for an installed wheel (where
# bento is a top-level namespace package). good_citizen itself is importable because
# this conftest sits at the package root (python/), which pytest adds to sys.path.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "gen" / "python"))
