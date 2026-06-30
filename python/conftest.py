# put the generated gen/python tree on the path for tests, so `from bento.v1 import
# bento_pb2 / bento_fsm` resolves the same way it does for an installed wheel (where
# bento is a top-level namespace package). The hand-written frood modules (frood.emit,
# frood.register, ...) resolve because this conftest sits at the package root (python/),
# which pytest adds to sys.path. frood is a PEP 420 NAMESPACE package, so the SAME `frood`
# name also spans the generated frood.v1 under gen/python/frood -- which is why the
# register-client's `from frood.v1 import frood_pb2` resolves here as it does in the wheel.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "gen" / "python"))
