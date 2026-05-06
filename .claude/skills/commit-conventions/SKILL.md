---
name: commit-conventions
description: How to format commit messages in ping-cloud-base
---

Commits use a Jira ticket prefix format:

```
PDO-XXXX: Brief description of what changed
```

- Prefix is the Jira issue ID in uppercase (`PDO-XXXX`)
- Description after the colon is concise (one line preferred)
- Use `[skip pipeline]` at the start of the message only when the change should not trigger CI (e.g., docs-only or profile-only changes)
- Feature branches are squash-merged into release branches — individual WIP commits on a branch don't need to follow this format strictly, but the final squashed commit should

If no Jira ticket is associated with the change, use a short descriptive message without a prefix.
