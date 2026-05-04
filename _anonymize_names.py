"""
Reference script documenting the anonymization mapping.

All real-sounding person names in the prototype have been replaced with
person_NNN placeholders to avoid any possibility of accidentally matching
real Morgan Stanley employees. The mapping is grouped by role:

  Sponsors (BU heads):       person_001 - person_004
  Validators:                person_005 - person_008
  WM Tech owners:            person_009 - person_012
  IB Tech owners:            person_013 - person_016
  AM Tech owners:            person_017 - person_019
  GF Tech owners:            person_020 - person_022

This script was used once to rewrite all source files; it is kept in the repo
as documentation of the anonymization scheme.
"""
import re
from pathlib import Path

NAME_MAP = {
    # ---- Sponsors (Heads of BU Tech) -----------------------------------------
    "Andrea Lombardi": "person_001",
    "Robert Hayes":    "person_002",
    "Catherine Yu":    "person_003",
    "Vikram Joshi":    "person_004",

    # ---- Validators (independent reviewers) ----------------------------------
    "Daniel Park":     "person_005",
    "Amara Okonkwo":   "person_006",
    "Lukas Bauer":     "person_007",
    "Fatima Al-Hassan":"person_008",

    # ---- WM owners -----------------------------------------------------------
    "Priya Shah":      "person_009",
    "Marcus Chen":     "person_010",
    "Elena Rodriguez": "person_011",
    "David Kim":       "person_012",

    # ---- IB owners -----------------------------------------------------------
    "James Whitfield": "person_013",
    "Aisha Patel":     "person_014",
    "Tom O'Brien":     "person_015",
    "Sophia Liu":      "person_016",

    # ---- AM owners -----------------------------------------------------------
    "Hiroshi Tanaka":  "person_017",
    "Rachel Green":    "person_018",
    "Olivia Brooks":   "person_019",

    # ---- GF owners -----------------------------------------------------------
    "Karan Mehta":     "person_020",
    "Jennifer Wu":     "person_021",
    "Mike Sullivan":   "person_022",
}

# Files we need to update
FILES = [
    "data/generate_mock_data.py",
    "agents/aggregator.py",
    "agents/llm_client.py",
    "PITCH.md",
    "README.md",
]


def replace_all():
    project_root = Path(__file__).parent.parent
    for relpath in FILES:
        p = project_root / relpath
        if not p.exists():
            print(f"  SKIP (not found): {relpath}")
            continue
        text = p.read_text()
        original = text
        # Sort by length DESC so longer names match first (avoids partial matches)
        for name in sorted(NAME_MAP.keys(), key=len, reverse=True):
            text = text.replace(name, NAME_MAP[name])
        if text != original:
            p.write_text(text)
            n_changes = sum(text.count(v) for v in NAME_MAP.values()) - sum(original.count(v) for v in NAME_MAP.values())
            print(f"  UPDATED: {relpath}  ({n_changes} replacements)")
        else:
            print(f"  no changes: {relpath}")


if __name__ == "__main__":
    replace_all()
