---
name: Bug report
about: Report a problem so it can be reproduced and fixed
title: "[bug] "
labels: bug
---

**Describe the bug**
A clear description of what went wrong.

**To reproduce**
Steps to reproduce (include the repository URI ingested, the question/diff, and
the endpoint if relevant).

**Expected vs. actual**
What you expected to happen, and what actually happened.

**Diagnostics**
- `/health` output (redact secrets)
- Relevant API response or worker/API log lines

**Environment**
- Deployment: local Docker / cloud (Render+Vercel) / other
- Backend version (`/health/live` → `version`)
- OS / browser (for frontend issues)
