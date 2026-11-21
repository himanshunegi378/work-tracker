# Agent skills

`samta-tracker/SKILL.md` teaches AI agents to drive the `samta-tracker` CLI (install the
Work Tracker app first). This folder is the source of truth.

Install, any of:

    samta-tracker install-skill                       # Claude Code, from the installed app
    samta-tracker install-skill --dir <agent skills>  # another agent's skills folder
    npx skills add <owner>/<repo>                     # skills.sh installer, many agents

After editing the skill, run `python scripts/sync_skill.py` (copies it into `src/cli/skill/`,
which ships inside the app; a test checks they match).
