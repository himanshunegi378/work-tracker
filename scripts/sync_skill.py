"""Copy the source skill (skills/samta-tracker/SKILL.md) into the package.

`skills/` is what `npx skills add` and humans read; `src/cli/skill/SKILL.md` is the copy that
ships inside the installed app for `samta-tracker install-skill`. Run after editing the skill.
A test fails if the two differ.
"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
shutil.copyfile(root / "skills/samta-tracker/SKILL.md", root / "src/cli/skill/SKILL.md")
print("synced")
