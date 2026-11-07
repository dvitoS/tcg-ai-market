"""Nightly scheduling is GitHub Actions only.

Local Windows Task Scheduler / crontab installers are retired so the catalog
and JustTCG drip cannot double-run outside CI. Use the workflow instead:

  .github/workflows/nightly_update.yml
  Actions → Nightly TCG Database & AI Update → Run workflow
"""

from __future__ import annotations

import sys


WORKFLOW = ".github/workflows/nightly_update.yml"
ACTIONS_HINT = (
    "Nightly runs only on GitHub Actions (03:00 UTC schedule + workflow_dispatch).\n"
    f"  Workflow: {WORKFLOW}\n"
    "  Repo → Actions → \"Nightly TCG Database & AI Update\" → Run workflow\n"
    "Do not install a local Task Scheduler / crontab job for nightly_update.py.\n"
    "One-off local debug: NIGHTLY_ALLOW_LOCAL=1 python nightly_update.py"
)


def main() -> int:
    print(ACTIONS_HINT)
    print(
        "\nschedule_setup.py no longer creates OS schedulers "
        "(retired — GitHub Actions is the only production runner).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
