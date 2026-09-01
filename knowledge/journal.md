# Journal: dated learn-back log

Append-only, one entry per learned technique. This file exists so hunt_recall finds dated
prior art that does not yet belong in a playbook class. When an entry hardens into a class
(battle-tested, proof bar validated), promote it into playbook.md and leave a stub line here
pointing at the class number.

Entry format (keep every field, one screen max):

```md
## YYYY-MM-DD - <technique in one imperative line>
- Engagement type: mobile / web / infra / mixed (anonymized, no client names)
- Signal: what made us look
- Technique: the exact commands or code shape that worked
- Proof bar: what evidence converted it (or why it stayed a lead)
- Status: LEAD / PROVEN / RETRACTED / PROMOTED to playbook class N
```

Rules:
- No target names, no client names, no raw secrets. Techniques and shapes only.
- A RETRACTED entry is as valuable as a PROVEN one: it kills a repeat detour.
- After every engagement (workflow.md: after the report ships), append what was new.
- Techniques that repeat across two engagements get promoted into playbook.md.
