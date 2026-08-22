---
name: apply-agent-profile
description: Synchronize model values from .cursor/agent-system.json into the matching project custom-agent frontmatter and validate exact agreement without a generator script.
disable-model-invocation: true
---

# Apply Agent Profile

Manual invocation only: `/apply-agent-profile`.

1. Read `.cursor/agent-system.json` and validate it as JSON.
2. For every key in `roles`, open `.cursor/agents/<role>.md`.
3. Confirm frontmatter `name` equals the role key.
4. Edit only the frontmatter `model` value to equal `roles.<role>.model`.
5. Do not generate files, use another configuration language, or change role instructions.
6. Re-read every agent and compare configured and frontmatter models exactly.
7. Run:

   `.\.venv\Scripts\python.exe -m pytest tests/docs/test_cursor_agent_system.py -q`

8. Report each role, desired model, resulting model, and validation result. If Cursor cannot
   reliably pin a configured model variant, report the limitation and leave the intended value
   explicit; never silently substitute a more expensive model.
