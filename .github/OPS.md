# Ops Control Plane

ChatOps-driven operations workflow for managing staging and production environments through GitHub issue commands.

## What

A GitHub Actions workflow that provides operational control over deployed applications through ChatOps commands posted on a designated "Ops Console" issue. Supports restart, redeploy, and rollback operations for both staging and production environments.

**Key characteristics:**
- **Triggers:** ChatOps (issue comments) + workflow_dispatch (manual UI)
- **Operations:** restart, redeploy, rollback
- **Environments:** staging (localhost:8001), production (localhost:8002)
- **Runner:** Self-hosted (required for local Docker access)
- **Security:** Issue-based access control, authorization allowlists, production confirmation gates
- **Rollback intelligence:** Primary source = GitHub Deployments API; Fallback = local history files
- **Audit trail:** All operations logged to designated Ops Console issue

---

## Why

### Problems Solved

| Problem | Solution in This Workflow | Status |
|---------|---------------------------|--------|
| **Rollback without open PR** | ChatOps commands work independently of PRs; no PR needed to rollback | ✅ Solved |
| **Production incident response** | Quick rollback via issue comment; no UI navigation required | ✅ Solved |
| **Restart without rebuild** | `restart` operation keeps same container, no image rebuild | ✅ Solved |
| **Safe production operations** | Requires `confirm=yes` flag for prod redeploy/rollback | ✅ Solved |
| **Unauthorized ops access** | Same authorization allowlists as deploy.yml | ✅ Solved |
| **ChatOps command injection** | Strict regex validation; no arbitrary code execution | ✅ Solved |
| **Rollback target calculation** | Uses GitHub Deployments API as primary source of truth | ✅ Solved |
| **Repeated rollbacks** | Handles "rollback of a rollback" correctly via deployment history | ✅ Solved |
| **Ops Console spam** | Commands only work on designated OPS_ISSUE_NUMBER | ✅ Solved |
| **Audit trail** | All operations post status to Ops Console issue | ✅ Solved |
| **Manual workflow dispatch** | Supports both ChatOps and GitHub Actions UI triggers | ✅ Solved |
| **Workflow tampering** | `issue_comment` trigger runs from default branch only | ✅ Solved |
| **Database migrations during rollback** | No migration rollback mechanism | ❌ Not addressed |
| **Blue-green deployments** | Simple stop/start model, no zero-downtime switching | ❌ Not addressed |

---

## Architecture

### Command Grammar

**Staging operations:**
```
[staging-restart]
[staging-redeploy sha=<40-char-hex>]
[staging-rollback sha=<40-char-hex>]
[staging-rollback steps=N]
```

**Production operations (require `confirm=yes`):**
```
[prod-restart]
[prod-redeploy sha=<40-char-hex> confirm=yes]
[prod-rollback sha=<40-char-hex> confirm=yes]
[prod-rollback steps=N confirm=yes]
```

**Validation rules:**
- Commands must be exact (case-sensitive, no extra spaces)
- SHA must be full 40-character hex (lowercase)
- `steps` must be positive integer (e.g., `steps=1` means "previous deployment")
- Cannot mix `sha=` and `steps=` (mutually exclusive)
- Production redeploy/rollback MUST include `confirm=yes`
- Commands only work on designated Ops Console issue (configured via `OPS_ISSUE_NUMBER`)

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ User comments ops command on Ops Console issue                      │
│ OR manually triggers via workflow_dispatch UI                       │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Workflow runs from DEFAULT BRANCH (main) - security boundary        │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: Parse and Validate Command                                 │
│  • Strict regex validation against command grammar                  │
│  • Extract: environment, action, sha (if any), steps (if any)      │
│  • Verify command source is OPS_ISSUE_NUMBER                        │
│  • Check user authorization (same allowlists as deploy.yml)        │
│  • For production redeploy/rollback: verify confirm=yes            │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ├─ FAIL ──> Post error comment, exit
                     │
                     ▼ PASS
┌─────────────────────────────────────────────────────────────────────┐
│                   OPERATION FORK                                    │
└──────┬──────────────────┬──────────────────┬───────────────────────┘
       │                  │                  │
   restart           redeploy           rollback
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐  ┌──────────────┐  ┌─────────────────────────────────┐
│ RESTART:    │  │ REDEPLOY:    │  │ ROLLBACK:                       │
│             │  │              │  │                                 │
│ 1. Stop     │  │ 1. Checkout  │  │ 1. Determine target SHA:        │
│    container│  │    target SHA│  │    • If sha= provided: use it   │
│ 2. Start    │  │ 2. Verify    │  │    • If steps= provided:        │
│    container│  │    image     │  │      a. Query GitHub            │
│    (same    │  │    exists    │  │         Deployments API         │
│    image)   │  │    (staging: │  │      b. Filter successful       │
│ 3. Health   │  │    may need  │  │         deployments for env     │
│    check    │  │    rebuild,  │  │      c. Calculate target index  │
│             │  │    prod: no  │  │         (current + steps)       │
│             │  │    rebuild)  │  │      d. Fallback: local history │
│             │  │ 3. Stop/rm   │  │         /tmp/myapp-{env}.history│
│             │  │    old       │  │ 2. Checkout target SHA          │
│             │  │ 4. Run new   │  │ 3. Verify image exists          │
│             │  │ 5. Health    │  │ 4. Stop/rm old container        │
│             │  │    check     │  │ 5. Run with target SHA image    │
│             │  │              │  │ 6. Health check                 │
└─────────────┘  └──────────────┘  └─────────────────────────────────┘
       │                  │                  │
       └──────────────────┴──────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Post operation status to Ops Console issue                         │
│  • Success: details table with SHA, timestamp, URL                  │
│  • Failure: error message with workflow logs link                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Rollback Logic Detail

**Primary source: GitHub Deployments API**

1. Query all deployments for repository
2. Filter by target environment (staging or production)
3. For each deployment, check its statuses
4. Keep only deployments with at least one "success" status
5. Build deduplicated array of successful deployment SHAs (newest first)
6. Calculate target index:
   - If current SHA found in history: `targetIndex = currentIndex + stepsBack`
   - If current SHA not found (baseline case): `targetIndex = stepsBack` (treat newest as index 0)
7. Validate bounds: ensure targetIndex < array length
8. Return SHA at targetIndex

**Fallback: Local history files**

- Path: `/tmp/myapp-{env}.history`
- Format: Append-only log with entries like:
  ```
  2024-02-24T10:30:00Z action=rollback sha=abc123def456...
  2024-02-24T10:15:00Z action=redeploy sha=def456abc123...
  ```
- Filtering: Only extract SHA-based entries (excludes `action=restart` which has no SHA)
- Reverse to newest-first order
- Same indexing logic as API source

**Why dual tracking?**
- GitHub Deployments API is authoritative but may be incomplete (older repos, manual deployments)
- Local history provides complete audit trail on runner machine
- Fallback ensures rollback works even if API data is unavailable

---

## Prerequisites

### 1. Self-Hosted Runner

Same as deploy.yml workflow. See [README.md](README.md#prerequisites) for setup.

### 2. Docker

Same as deploy.yml workflow. Containers must be running:
- `myapp-staging` on port 8001
- `myapp-prod` on port 8002

### 3. Ops Console Issue

**Create a designated Ops Console issue:**

1. Navigate to repository → Issues → New issue
2. Title: "🚦 Ops Console — Staging & Production Control Plane"
3. Body (example):
   ```markdown
   # ChatOps Interface

   This issue serves as the control plane for operational commands.

   ## Available Commands

   **Staging:**
   - `[staging-restart]` - Restart staging container (no rebuild)
   - `[staging-redeploy sha=<sha>]` - Redeploy staging to specific commit
   - `[staging-rollback steps=N]` - Rollback staging N deployments

   **Production (requires confirm=yes):**
   - `[prod-restart]` - Restart production container
   - `[prod-redeploy sha=<sha> confirm=yes]` - Redeploy production to specific commit
   - `[prod-rollback steps=1 confirm=yes]` - Rollback production to previous deployment

   ## Authorized Users
   - ktamvada-cyber
   - gromag
   ```
4. Create issue and note the issue number (e.g., `#2`)

**Configure OPS_ISSUE_NUMBER in workflow:**

Edit `.github/workflows/ops.yml` line 51:
```yaml
env:
  OPS_ISSUE_NUMBER: 2  # Replace with your Ops Console issue number
```

**Security note:** Commands posted on ANY other issue will be rejected with error message.

### 4. GitHub Environment Secrets

Same as deploy.yml workflow. Ensure `staging` and `production` environments have:
- `API_KEY` secret
- `DB_HOST` secret

### 5. GitHub Environment Protection

**Production environment MUST have:**
- Required reviewers (at least 1)
- Same configuration as deploy.yml workflow

**Staging environment:**
- No protection needed (auto-executes)

### 6. Authorized Users

Authorization allowlists are defined in workflow (lines 80-88 in ops.yml):

```javascript
const stagingAuthorizedUsers = [
  'ktamvada-cyber',
  'gromag'
];

const productionAuthorizedUsers = [
  'ktamvada-cyber',
  'gromag'
];
```

Edit these arrays to match your team.

---

## How to Use

### Via ChatOps (Issue Comments)

**Prerequisites:**
- Ops Console issue created and configured
- User is in authorization allowlist
- Containers are running (at least one successful deployment from deploy.yml)

#### Restart Operation

**Use case:** Container is unresponsive but image is good; restart without rebuilding.

```
[staging-restart]
```

**What happens:**
1. Stops current container
2. Starts container with same image
3. Runs health check (10 retries, 2s interval)
4. Posts status to Ops Console

**When to use:**
- Memory leak suspected (restart clears)
- Application hung but code is fine
- Quick recovery during incident

**When NOT to use:**
- Need to deploy different code (use redeploy or rollback instead)
- Container won't start due to image corruption (redeploy instead)

#### Redeploy Operation

**Use case:** Deploy a specific commit SHA to environment.

```
[staging-redeploy sha=abc123def456789012345678901234567890abcd]
```

**What happens:**
1. Validates SHA format (must be 40-char hex)
2. Checks out target commit
3. For staging: Builds Docker image if not exists
4. For production: Verifies image exists (no rebuild allowed)
5. Stops/removes old container
6. Runs new container with target SHA image
7. Health check
8. Appends to local history: `/tmp/myapp-{env}.history`

**When to use:**
- Deploy a known-good commit during incident
- Forward-deploy to specific SHA (not necessarily latest)

**Production example (requires confirmation):**
```
[prod-redeploy sha=abc123def456789012345678901234567890abcd confirm=yes]
```

#### Rollback Operation

**Use case:** Revert to previous deployment (most common incident response).

**Rollback by steps (recommended):**
```
[staging-rollback steps=1]
```

Where `steps=1` means "previous deployment", `steps=2` means "2 deployments ago", etc.

**What happens:**
1. Queries GitHub Deployments API
2. Filters deployments for target environment with "success" status
3. Builds deduplicated SHA array (newest first)
4. Finds current SHA in array
5. Calculates target: `currentIndex + steps`
6. If current SHA not found, treats newest as baseline: `targetIndex = steps`
7. Falls back to local history if API query fails
8. Validates bounds (ensures target exists)
9. Checks out target SHA
10. Verifies image exists
11. Stops/removes old container
12. Runs container with target SHA image
13. Health check
14. Posts status showing which source was used (API vs local history)

**Rollback by SHA (when you know exact target):**
```
[staging-rollback sha=def456abc123...]
```

Simpler flow: directly deploy specified SHA (no history lookup needed).

**Production rollback (requires confirmation):**
```
[prod-rollback steps=1 confirm=yes]
```

**Safety rules:**
- Cannot mix `sha=` and `steps=` (mutually exclusive)
- Production rollback requires `confirm=yes`
- Bounds checking prevents "steps too large" errors

**Example workflow:**
```
# Scenario: Production deployment of commit C is broken; rollback to commit B

# History (from Deployments API):
# Index 0: sha=cccc... (current, broken)
# Index 1: sha=bbbb... (previous, good)
# Index 2: sha=aaaa... (older)

# Command:
[prod-rollback steps=1 confirm=yes]

# Result: Deploys sha=bbbb...
```

**Repeated rollback handling:**
```
# Scenario: Rolled back to B, but B is also broken; rollback to A

# History after first rollback:
# Index 0: sha=bbbb... (current, after first rollback)
# Index 1: sha=cccc... (the broken one we rolled back from)
# Index 2: sha=aaaa... (oldest)

# Command:
[prod-rollback steps=1 confirm=yes]

# Result: Deploys sha=cccc... (the one we rolled back from)
# To skip it and go to sha=aaaa, use steps=2 instead
```

### Via Workflow Dispatch (Manual UI)

**When to use:** Ops Console issue is unavailable, or prefer UI interaction.

**Steps:**
1. Navigate to Actions → "Ops Control Plane" workflow
2. Click "Run workflow" dropdown
3. Select inputs:
   - **Environment:** staging or production
   - **Action:** restart, redeploy, or rollback
   - **SHA:** (optional) Full 40-char commit SHA (required for rollback/redeploy unless steps provided)
   - **Steps:** (optional) Rollback steps (used only for rollback; default=1)
   - **Confirm:** (required for production) Type "yes"
4. Click "Run workflow"
5. Check workflow logs in Actions tab

**Example: Production rollback via UI**
```
Environment: production
Action: rollback
SHA: (leave empty)
Steps: 1
Confirm: yes
```

---

## Security Model

### Issue-Based Access Control

**OPS_ISSUE_NUMBER restriction (line 51 in ops.yml):**

Only commands posted on the designated Ops Console issue are processed. Commands on other issues are rejected:

```markdown
❌ SECURITY: Commands only accepted on Ops Console issue #2
This comment was posted on issue #5
```

**Why:** Prevents unauthorized users from creating their own issues to bypass authorization.

### Authorization Allowlists

Same allowlists as deploy.yml workflow (lines 80-88):
- Staging: ktamvada-cyber, gromag
- Production: ktamvada-cyber, gromag

Violations post error:
```markdown
❌ AUTHORIZATION FAILED: User "bob" is not authorized for production operations.
Authorized users: ktamvada-cyber, gromag
```

### Production Confirmation Gate

Production `redeploy` and `rollback` operations REQUIRE `confirm=yes`:

```
[prod-rollback steps=1 confirm=yes]  ✅ Allowed
[prod-rollback steps=1]              ❌ Rejected
```

Rejection message:
```markdown
❌ VALIDATION FAILED: Production rollback requires confirm=yes flag
```

**Why:** Prevents accidental production changes via mistyped commands.

**Exception:** `restart` does NOT require confirmation (considered low-risk).

### Command Injection Prevention

Strict regex validation (line 112 in ops.yml):

```javascript
const commandRegex = /^\[(staging|prod)-(restart|redeploy|rollback)(?:\s+sha=([a-f0-9]{40}))?(?:\s+steps=(\d+))?(?:\s+confirm=(yes))?\]$/;
```

**Rejected commands:**
- `[staging-restart; rm -rf /]` - Extra characters
- `[staging-redeploy sha=$(whoami)]` - Shell injection attempt
- `[STAGING-RESTART]` - Case mismatch
- `[staging-restart ]` - Trailing space
- `[staging-rollback sha=abc123]` - SHA not 40 chars
- `[prod-rollback steps=1 sha=abc confirm=yes]` - Mixed sha/steps

All rejected with specific error messages.

### Default Branch Execution

For `issue_comment` trigger, GitHub always runs workflow from default branch (main), not from feature branches.

**Attack prevented:**
1. Attacker creates PR with modified `.github/workflows/ops.yml` that removes authorization
2. Attacker comments ops command on Ops Console issue
3. GitHub ignores feature branch workflow, executes main branch version
4. Authorization check remains intact

**Reference:** [GitHub Docs - issue_comment trigger](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#issue_comment)

---

## Concurrency Model

Configuration (lines 58-60 in ops.yml):

```yaml
concurrency:
  group: ops
  cancel-in-progress: true
```

**Behavior:**
- One ops operation at a time across all environments
- If op A is running and op B is triggered, op A is cancelled
- Separate from deploy.yml concurrency group (deploy and ops can run simultaneously)

**Why separate group:**
- Deploy operations (from deploy.yml) and ops operations (from ops.yml) are independent
- User can rollback while deploy is in progress (useful for incident response)

**Risks:**
- Same mid-teardown risk as deploy.yml (cancel during `docker stop` can leave container in stopped state)
- Mitigation: Both stop and rm use `|| true` to tolerate partial state

---

## Output and Observability

### Ops Console Comments

All operations post status to Ops Console issue.

**1. Validation failure:**
```markdown
### ❌ Operation Rejected

**Error Details:**

❌ VALIDATION FAILED: Production rollback requires confirm=yes flag

**Command:** [prod-rollback steps=1]
**User:** bob
**Environment:** production

---
📋 **View Full Logs:** [Workflow Run #123](https://github.com/...)
```

**2. Restart success:**
```markdown
### ✅ Restart Operation SUCCEEDED

#### 📋 Operation Details
| Field | Value |
|-------|-------|
| **Environment** | `staging` |
| **Operation** | restart |
| **Status** | SUCCEEDED |
| **Container** | `myapp-staging` |
| **Port** | `8001` |
| **Service Status** | ✅ Healthy (verified) |

---
#### 🌐 Access Information
**URL:** http://localhost:8001/
**Workflow Run:** [View Logs](https://github.com/...)
```

**3. Rollback success (API source):**
```markdown
### ✅ Rollback Operation SUCCEEDED

#### 📋 Operation Details
| Field | Value |
|-------|-------|
| **Environment** | `production` |
| **Operation** | rollback |
| **Status** | SUCCEEDED |
| **Target SHA** | `abc123def456...` |
| **Rollback Method** | steps-based (steps=1) |
| **Source** | GitHub Deployments API |
| **Container** | `myapp-prod` |
| **Port** | `8002` |
| **Service Status** | ✅ Healthy (verified) |

---
#### 🌐 Access Information
**URL:** http://localhost:8002/
**Workflow Run:** [View Logs](https://github.com/...)
```

**4. Rollback success (local history fallback):**
```markdown
### ✅ Rollback Operation SUCCEEDED

#### 📋 Operation Details
| Field | Value |
|-------|-------|
| **Environment** | `staging` |
| **Operation** | rollback |
| **Status** | SUCCEEDED |
| **Target SHA** | `def456abc123...` |
| **Rollback Method** | steps-based (steps=2) |
| **Source** | Local History (GitHub API unavailable) |
| **Container** | `myapp-staging` |
| **Port** | `8001` |
| **Service Status** | ✅ Healthy (verified) |

---
#### 🌐 Access Information
**URL:** http://localhost:8001/
**Workflow Run:** [View Logs](https://github.com/...)
```

**5. Operation failure:**
```markdown
### ❌ Redeploy Operation FAILED

#### 📋 Operation Details
| Field | Value |
|-------|-------|
| **Environment** | `production` |
| **Operation** | redeploy |
| **Status** | FAILED |
| **Target SHA** | `abc123...` |
| **Service Status** | ❌ Failed |

---
#### ⚠️ Action Required
Check workflow logs for detailed error information.
**Workflow Run:** [View Logs](https://github.com/...)
```

### Workflow Logs

**Access:** Repository → Actions → "Ops Control Plane" → Click specific run

**Key log sections:**
1. **Parse and validate command** - Command parsing, authorization check, confirmation validation
2. **Compute Rollback Target (GitHub Deployments API)** - API query, SHA array, target calculation
3. **Determine Target SHA** - Local history fallback if API failed
4. **Execute operation** - Docker commands, health check attempts
5. **Post operation status** - Comment posting confirmation

### Local History Files

**Path:** `/tmp/myapp-staging.history` and `/tmp/myapp-production.history`

**Format:**
```
2024-02-24T10:30:00Z action=rollback sha=abc123def456...
2024-02-24T10:15:00Z action=redeploy sha=def456abc123...
2024-02-24T10:00:00Z action=restart
```

**Viewing:**
```bash
# On runner machine
cat /tmp/myapp-staging.history
tail -10 /tmp/myapp-production.history  # Last 10 operations
```

**Rotation:** No automatic rotation. Manually truncate if file grows large:
```bash
# Keep last 100 lines
tail -100 /tmp/myapp-staging.history > /tmp/myapp-staging.history.tmp
mv /tmp/myapp-staging.history.tmp /tmp/myapp-staging.history
```

---

## Testing

### Quick Smoke Test

**Prerequisites:** At least one successful deployment from deploy.yml workflow.

```bash
# 1. Test staging restart
Comment on Ops Console: [staging-restart]
Expected: Container restarts, health check passes

# 2. Test staging rollback
Comment on Ops Console: [staging-rollback steps=1]
Expected: Rolls back to previous deployment

# 3. Test production restart
Comment on Ops Console: [prod-restart]
Expected: May require approval gate, then restarts

# 4. Test production rollback with confirmation
Comment on Ops Console: [prod-rollback steps=1 confirm=yes]
Expected: Approval gate, then rollback to previous production deployment
```

### Comprehensive Test Scenarios

#### Security and Authorization

| Test Case | Command | Expected Result |
|-----------|---------|-----------------|
| Unauthorized user | `[staging-restart]` posted by user not in allowlist | ❌ Rejected with authorization error |
| Wrong issue | `[staging-restart]` posted on issue #5 (not Ops Console) | ❌ Rejected with "Commands only accepted on Ops Console issue #2" |
| Production without confirm | `[prod-rollback steps=1]` (missing `confirm=yes`) | ❌ Rejected with "requires confirm=yes flag" |
| Invalid command format | `[STAGING-RESTART]` (uppercase) | ❌ Rejected with "Invalid command format" |
| Command injection attempt | `[staging-restart; rm -rf /]` | ❌ Rejected (no regex match) |

#### Restart Operations

| Test Case | Command | Expected Result |
|-----------|---------|-----------------|
| Staging restart | `[staging-restart]` | ✅ Container stops and starts with same image |
| Production restart | `[prod-restart]` | ✅ May require approval, then restarts |
| Restart with no container | `[staging-restart]` when no container exists | ❌ Fails (docker start fails on non-existent container) |

#### Redeploy Operations

| Test Case | Command | Setup | Expected Result |
|-----------|---------|-------|-----------------|
| Staging redeploy to existing SHA | `[staging-redeploy sha=abc...]` | SHA exists in repo | ✅ Builds image if needed, deploys |
| Production redeploy | `[prod-redeploy sha=abc... confirm=yes]` | Image exists from staging | ✅ Deploys (no rebuild) |
| Production redeploy without staging | `[prod-redeploy sha=xyz... confirm=yes]` | Image doesn't exist | ❌ Fails with "Image does not exist" |
| Invalid SHA format | `[staging-redeploy sha=abc123]` | SHA not 40 chars | ❌ Rejected with "Invalid command format" |

#### Rollback Operations

| Test Case | Command | Setup | Expected Result |
|-----------|---------|-------|-----------------|
| Rollback by steps (basic) | `[staging-rollback steps=1]` | At least 2 deployments exist | ✅ Rolls back to previous deployment |
| Rollback by SHA | `[staging-rollback sha=abc...]` | SHA exists in history | ✅ Deploys specified SHA |
| Rollback steps out of bounds | `[staging-rollback steps=100]` | Only 3 deployments exist | ❌ Fails with bounds check error |
| Rollback with no history | `[staging-rollback steps=1]` | Fresh environment, no deployments | ❌ Fails (no history available) |
| Repeated rollback | `[staging-rollback steps=1]` twice | After first rollback, roll back again | ✅ Each rollback calculates target from current position |
| Production rollback | `[prod-rollback steps=1 confirm=yes]` | Multiple prod deployments | ✅ Requires approval, rolls back |
| Mixed sha and steps | `[staging-rollback sha=abc... steps=1]` | N/A | ❌ Rejected (mutually exclusive) |

#### Deployment History Accuracy

| Test Case | Action | Expected Local History Entry |
|-----------|--------|-------------------------------|
| Restart | `[staging-restart]` | `2024-...-...Z action=restart` (no SHA) |
| Redeploy | `[staging-redeploy sha=abc...]` | `2024-...-...Z action=redeploy sha=abc...` |
| Rollback | `[staging-rollback steps=1]` | `2024-...-...Z action=rollback sha=<target>` |

#### Error Handling

| Test Case | Scenario | Expected Result |
|-----------|----------|-----------------|
| Container doesn't exist | Run `docker stop myapp-staging` manually, then trigger redeploy | ✅ Workflow tolerates error (|| true), creates new container |
| Health check timeout | Deploy app that takes >20s to start | ⚠️ Deployment succeeds with "running_unverified" status |
| GitHub API unavailable | Disconnect network, trigger rollback by steps | ✅ Falls back to local history |
| Corrupted local history | Delete `/tmp/myapp-staging.history` | ❌ Rollback by steps fails (no history source) |

---

## FAQ and Troubleshooting

### Q: How do I find the Ops Console issue number?

**Solution:**
1. Create the issue in GitHub
2. Note the issue number from the URL: `https://github.com/org/repo/issues/2` → issue number is `2`
3. Update workflow line 51: `OPS_ISSUE_NUMBER: 2`

---

### Q: Commands posted on Ops Console are ignored

**Possible causes:**
1. Wrong issue number configured in workflow
2. Issue is closed (workflow only processes comments on open issues)
3. User is not in authorization allowlist
4. Command format is incorrect

**Debugging:**
```bash
# Check workflow logs in Actions tab
# Look for "Parse and validate command" step
# Error message will indicate specific validation failure
```

---

### Q: Production rollback rejected despite including `confirm=yes`

**Common mistakes:**
```
[prod-rollback steps=1 confirm=yes]   ✅ Correct
[prod-rollback steps=1 confirm=Yes]   ❌ Wrong (case-sensitive)
[prod-rollback steps=1 confirm= yes]  ❌ Wrong (space after =)
[prod-rollback steps=1 confirmation=yes]  ❌ Wrong (param name)
```

**Solution:** Use exact format: `confirm=yes` (lowercase, no spaces).

---

### Q: Rollback fails with "No rollback target found" or "steps out of bounds"

**Cause:** Not enough deployment history.

**Example:**
- Current deployment is the first ever deployment
- User runs `[staging-rollback steps=1]`
- Error: No previous deployment to roll back to

**Solution:**
1. Check deployment history: Repository → Environments → staging → View deployments
2. Verify at least `steps + 1` deployments exist (e.g., `steps=1` requires at least 2 deployments)
3. If insufficient history, redeploy to specific SHA instead:
   ```
   [staging-redeploy sha=<known-good-sha>]
   ```

---

### Q: Rollback uses local history instead of GitHub API

**Cause:** GitHub API query failed or returned no successful deployments.

**Possible reasons:**
1. Network issue connecting to GitHub API
2. No deployments have "success" status (all are "in_progress" or "failure")
3. Deployments were created before GitHub Deployments API integration added to deploy.yml

**Debugging:**
```bash
# On runner machine, check local history
cat /tmp/myapp-staging.history

# Compare with GitHub UI
# Repository → Environments → staging → View deployments
```

**Solution:** Local history fallback is normal and expected. Verify the deployed SHA is correct by checking:
```bash
docker inspect myapp-staging --format '{{.Config.Image}}'
# Should show: ci-demo:<target-sha>
```

---

### Q: "Image does not exist" error during production redeploy

**Cause:** Trying to deploy SHA that hasn't been built for staging.

**Solution:**
1. Deploy to staging first:
   ```
   [staging-redeploy sha=abc123...]
   ```
2. Wait for staging deployment to succeed
3. Then deploy to production:
   ```
   [prod-redeploy sha=abc123... confirm=yes]
   ```

**Why:** Production never rebuilds images; must reuse staging images for safety.

---

### Q: Health check shows "running_unverified" instead of "healthy"

**Same as deploy.yml workflow.** See [README.md FAQ](README.md#q-health-check-shows-running_unverified-instead-of-healthy).

**Quick debug:**
```bash
docker logs myapp-staging  # Check if app started
curl http://localhost:8001/  # Test endpoint manually
```

---

### Q: Can I rollback to a deployment from 2 weeks ago?

**Yes, if:**
1. SHA still exists in deployment history (GitHub API or local history)
2. Docker image still exists on runner machine

**Steps:**

**Option 1: Rollback by steps**
```bash
# First, count deployments
# Repository → Environments → staging → View deployments
# Count from current (index 0) to target deployment

# If target is 10 deployments ago:
[staging-rollback steps=10]
```

**Option 2: Rollback by SHA (easier)**
```bash
# Find SHA from GitHub Environments UI or git log
[staging-rollback sha=abc123def456...]
```

**Caveat:** If Docker image was pruned, redeploy will rebuild for staging, but production redeploy will fail (can't rebuild). Workaround:
1. `[staging-redeploy sha=abc...]` to rebuild image
2. `[prod-redeploy sha=abc... confirm=yes]` to deploy to production

---

### Q: How do I automate rollback based on error rate?

**This workflow does NOT support automated rollback.** All operations require manual commands (ChatOps or workflow_dispatch).

**Future enhancement:** Integrate with monitoring (Prometheus, Datadog) to trigger workflow_dispatch automatically based on alerts. See [GitHub Actions workflow_dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event).

---

## Comparison with deploy.yml

| Feature | deploy.yml | ops.yml |
|---------|------------|---------|
| **Trigger** | PR comments (`[staging]`, `[prod]`) | Ops Console issue comments + workflow_dispatch |
| **Primary use case** | Deploy code from PR to environments | Manage already-deployed environments |
| **Requires open PR** | Yes | No |
| **Operations** | Deploy only | restart, redeploy, rollback |
| **Image building** | Always for staging, never for prod | Only for staging redeploy if image missing |
| **Rollback support** | None (can only deploy forward) | Full rollback with history tracking |
| **Authorization** | Per-environment allowlists | Same allowlists (shared security model) |
| **Audit trail** | PR comments + Actions logs | Ops Console issue comments + Actions logs |
| **Concurrency group** | `deployment` | `ops` (independent) |
| **Best for** | PR-based deployments, testing features | Incident response, operational fixes |

**When to use deploy.yml:**
- Deploying new feature from PR to staging for testing
- Promoting staging deployment to production after PR approval

**When to use ops.yml:**
- Production incident: rollback to previous version
- Restart unresponsive container without changing code
- Deploy specific commit without opening PR (e.g., hotfix from old branch)
- Operational maintenance (bounce containers, redeploy same version with new secrets)

**Can both run simultaneously?**
Yes, they use separate concurrency groups. Example:
- deploy.yml is deploying PR #123 to staging (takes 5 minutes for build)
- User triggers `[prod-rollback steps=1 confirm=yes]` via ops.yml
- Both workflows run in parallel without interfering

---

## Next Steps

1. **Create Ops Console issue** and configure `OPS_ISSUE_NUMBER`
2. **Test restart operation** in staging: `[staging-restart]`
3. **Test rollback** in staging after multiple deployments
4. **Practice incident response** by simulating production rollback
5. **Review authorization allowlists** and add/remove users as needed
6. **Set up monitoring** to track deployment history and rollback frequency
7. **Consider enhancing** with automated rollback triggers based on error rates

---

## Quick Reference

### ChatOps Commands

**Staging:**
```
[staging-restart]
[staging-redeploy sha=<40-char-hex>]
[staging-rollback sha=<40-char-hex>]
[staging-rollback steps=N]
```

**Production:**
```
[prod-restart]
[prod-redeploy sha=<40-char-hex> confirm=yes]
[prod-rollback sha=<40-char-hex> confirm=yes]
[prod-rollback steps=N confirm=yes]
```

### Common Tasks

```bash
# View deployment history
cat /tmp/myapp-staging.history
cat /tmp/myapp-production.history

# Check running containers
docker ps

# Verify deployed SHA
docker inspect myapp-staging --format '{{.Config.Image}}'
docker inspect myapp-prod --format '{{.Config.Image}}'

# View container logs
docker logs myapp-staging
docker logs myapp-prod

# Test endpoints
curl http://localhost:8001/
curl http://localhost:8002/

# Clean up history files (if too large)
tail -100 /tmp/myapp-staging.history > /tmp/myapp-staging.history.tmp
mv /tmp/myapp-staging.history.tmp /tmp/myapp-staging.history
```

### GitHub UI Navigation

- **Ops Console:** Repository → Issues → [Your Ops Console issue #]
- **Workflow runs:** Repository → Actions → "Ops Control Plane"
- **Deployment history:** Repository → Environments → staging/production
- **Workflow file:** `.github/workflows/ops.yml`

### Authorized Users (default)

- ktamvada-cyber
- gromag

(Edit workflow lines 80-88 to customize)

### File Locations

- Workflow: `.github/workflows/ops.yml`
- Documentation: `.github/OPS.md`
- Local history (staging): `/tmp/myapp-staging.history`
- Local history (production): `/tmp/myapp-production.history`
