# Agent skills

`samta-tracker/SKILL.md` teaches AI agents (Claude Code and compatible) to drive the
`samta-tracker` CLI. Install the app first, then copy the skill folder:

    # Claude Code, for all projects
    mkdir -p ~/.claude/skills && cp -r skills/samta-tracker ~/.claude/skills/

    # or only for one project
    mkdir -p .claude/skills && cp -r skills/samta-tracker .claude/skills/

Then ask your agent, e.g. "log 1h on <project> for code review" or "start the tracker".
