"""Path-loadable sheep-first meta bench (current_phase.md §Β.2).

``get_last_callable`` selects the last callable in this file, so compare()/play()
can take this path string as the sheep-first opponent.
"""
import os
import sys

# Same loader constraint as meta_route.py: __file__ may be absent under get_last_callable.
def _ensure_repo_root_on_path() -> None:
    candidates = []
    try:
        candidates.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    except NameError:
        pass
    for entry in list(sys.path):
        if not entry:
            continue
        abs_entry = os.path.abspath(entry)
        if os.path.basename(abs_entry) == "bench_agents":
            candidates.append(os.path.abspath(os.path.join(abs_entry, "..", "..")))
    candidates.append(os.getcwd())
    for root in candidates:
        if os.path.isdir(os.path.join(root, "agent")) and os.path.isdir(os.path.join(root, "harness")):
            if root not in sys.path:
                sys.path.insert(0, root)
            return


_ensure_repo_root_on_path()

from harness.bench_agents.meta_route import meta_route_sheep  # noqa: E402

agent = meta_route_sheep
