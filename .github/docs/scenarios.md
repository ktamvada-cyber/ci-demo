# Operational Scenarios (Canonical: ../README.md)

**This document is retained for backwards compatibility.**

✅ **Canonical scenario documentation is now in:**
- [`.github/README.md`](../README.md) → **Operational Scenarios** section
- [`.github/OPS.md`](../OPS.md) → **Ops Control Plane scenarios**

---

## Quick Links

If you're looking for:
- **Deployment scenarios** → See [README.md - Operational Scenarios](../README.md#operational-scenarios)
- **Rollback scenarios** → See [OPS.md - Rollback Logic](../OPS.md#rollback-logic-detail)
- **Production incident playbook** → See [README.md - Production Incident Playbook](../README.md#production-incident-playbook)
- **Common patterns** → See [README.md - How to Use](../README.md#how-to-use)
- **Edge cases** → See [README.md - FAQ and Troubleshooting](../README.md#faq-and-troubleshooting)

---

## Migration Note

The scenario walkthroughs have been consolidated to:
- Reduce documentation drift
- Avoid duplication with README.md
- Consolidate operational knowledge
- Improve discoverability

**Previous content:** This file previously contained 13 detailed scenario walkthroughs (A-M). The essential scenarios have been consolidated into README.md's "Operational Scenarios" section.

**Key scenarios now in README.md:**
- Happy path staging deployment
- Happy path production deployment
- Authorization failures
- Already deployed detection
- Merge conflict validation
- Production incident response

**Extended scenarios in OPS.md:**
- Restart operations
- Redeploy operations
- Rollback-by-steps operations
- Rollback-by-SHA operations

**History preserved:** Original detailed walkthroughs are available in git history if needed for reference.

---

For operational documentation, see:
- [README.md - Operational Scenarios](../README.md#operational-scenarios)
- [OPS.md - Ops Control Plane](../OPS.md)
- [operations.md - Daily Runbooks](operations.md)
