# Deploy-on-Comment Workflow

PR-comment-triggered deployment system for local staging and production environments.

## What

A GitHub Actions workflow that deploys code to local Docker containers when authorized users comment `[staging]` or `[prod]` on open pull requests. The workflow validates PRs, builds Docker images tagged by commit SHA, and deploys to simulated staging (localhost:8001) or production (localhost:8002) environments.

**Key characteristics:**
- **Trigger:** PR comments (`[staging]` or `[prod]`)
- **Environments:** Two local Docker containers (myapp-staging on port 8001, myapp-prod on port 8002)
- **Runner:** Self-hosted (required for local Docker access)
- **Deployment unit:** Exact commit SHA (not branch names)
- **Gating:** Production requires manual approval via GitHub Environment protection
- **Image handling:** Staging builds new images; production reuses staging images (never rebuilds)

---

## Why

### Problems Solved

| Problem | Solution in This Workflow | Status |
|---------|---------------------------|--------|
| **Hitchhiker commits** (attacker adds malicious commits after approval) | SHA-based deployment: deploys exact commit SHA at comment time, not branch tip | ✅ Solved |
| **Untested production deployments** | Production must reuse staging image; fails if staging image doesn't exist | ✅ Solved |
| **Unauthorized deployments** | Per-environment allowlists; only ktamvada-cyber and gromag can trigger | ✅ Solved |
| **Deploying conflicted PRs** | Validates `mergeable_state == "clean"` and `mergeable != false` before deployment | ✅ Solved |
| **Deploying closed PRs** | Checks PR state is "open" | ✅ Solved |
| **Workflow tampering in feature branches** | `issue_comment` trigger always runs from default branch (main), ignoring feature branch workflow modifications | ✅ Solved |
| **Redundant redeployments** | Detects if target SHA is already running; skips deployment and posts notification | ✅ Solved |
| **Self-serve QA testing** | Authorized users can deploy to staging on demand via PR comment | ✅ Solved |
| **Audit trail of who deployed what** | GitHub Actions logs + PR comments record deployer, SHA, timestamp, approval chain | ✅ Solved |
| **Production approval gate** | GitHub Environment "production" requires designated reviewers to approve before deployment proceeds | ✅ Solved |
| **Database migrations** | No migration execution mechanism | ❌ Not addressed |
| **Rollback without open PR** | Can only deploy via PR comments; no standalone rollback trigger | ⚠️ Partial (can comment on old PR) |
| **Multi-runner artifact sharing** | Images stored locally on self-hosted runner; no registry push/pull | ❌ Not addressed |
| **Health check verification of actual deployment** | Checks `GET /` responds, but does not verify returned commit SHA matches deployed SHA | ⚠️ Partial |
| **Concurrent deployment queueing** | Uses `cancel-in-progress: true`; newer deployment cancels older (risks aborting mid-teardown) | ⚠️ Partial (works but risky) |

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ User comments [staging] or [prod] on open PR                        │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Workflow runs from DEFAULT BRANCH (main) regardless of PR branch    │
│ Security: Feature branch cannot tamper with workflow logic          │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: Validate                                                    │
│  • Is comment exactly "[staging]" or "[prod]"?                      │
│  • Is commenter authorized? (staging: ktamvada-cyber, gromag;       │
│                              prod: ktamvada-cyber, gromag)          │
│  • Is PR state "open"?                                              │
│  • Is mergeable_state "clean"?                                      │
│  • Are there merge conflicts? (mergeable != false)                  │
│  • Extract PR HEAD SHA (exact commit to deploy)                     │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ├─ FAIL ──> Post rejection comment, exit
                     │
                     ▼ PASS
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1.5: Create GitHub Deployment (via API)                       │
│  • Create deployment record with ref = PR head SHA                  │
│  • Set initial status to "in_progress"                              │
│  • Provides correct branch/SHA visibility in GitHub UI              │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Checkout exact SHA (not branch)                            │
│  • git checkout <PR_HEAD_SHA>                                       │
│  • Never use branch name; prevents hitchhiker attacks               │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Capture metadata                                           │
│  • BUILD_TIMESTAMP (ISO 8601)                                       │
│  • DEPLOYMENT_ID (GitHub run ID)                                    │
│  • COMMIT_SHA (40-char full SHA)                                    │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: Check if already deployed                                  │
│  • docker inspect myapp-{environment} --format '{{.Config.Image}}'  │
│  • If running image == ci-demo:<SHA>, skip deployment              │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ├─ ALREADY DEPLOYED ──> Post "skipped" comment, exit
                     │
                     ▼ NOT DEPLOYED
┌─────────────────────────────────────────────────────────────────────┐
│                   ENVIRONMENT FORK                                  │
└─────────────┬───────────────────────────────────┬───────────────────┘
              │                                   │
       [staging] │                            [prod] │
              │                                   │
              ▼                                   ▼
┌──────────────────────────┐      ┌──────────────────────────────────┐
│ STEP 5a: Deploy Staging │      │ GitHub Environment Protection    │
│  • docker stop/rm old    │      │ Pauses here for manual approval  │
│  • docker build          │      │ Sends notifications to reviewers │
│    --build-arg SHA       │      │ Wait for 1 reviewer to approve   │
│    --build-arg TIMESTAMP │      └───────────┬──────────────────────┘
│    -t ci-demo:<SHA>      │                  │
│  • docker run -d         │                  ▼ APPROVED
│    -p 8001:8000          │      ┌──────────────────────────────────┐
│    --name myapp-staging  │      │ STEP 5b: Verify Staging Image   │
│  • Health check:         │      │  • docker image inspect          │
│    curl localhost:8001/  │      │    ci-demo:<SHA>                 │
│  • Post success comment  │      │  • FAIL if image doesn't exist   │
└──────────────────────────┘      │    (forces staging-first flow)   │
                                  └───────────┬──────────────────────┘
                                              │
                                              ▼
                                  ┌──────────────────────────────────┐
                                  │ STEP 5c: Deploy Production       │
                                  │  • docker stop/rm old            │
                                  │  • docker run -d                 │
                                  │    -p 8002:8000                  │
                                  │    --name myapp-prod             │
                                  │    ci-demo:<SHA>  ← REUSE image  │
                                  │  • NO REBUILD                    │
                                  │  • Health check:                 │
                                  │    curl localhost:8002/          │
                                  │  • Post success comment          │
                                  └──────────────────────────────────┘
```

### Deployment Steps Detail

**What this workflow CONTAINS:**

1. **Validation** (lines 47-167): Authorization, PR state, mergeable_state, conflict detection, SHA extraction
2. **GitHub Deployment creation** (lines 170-218): Create deployment record via API tied to PR head SHA (not main)
3. **Validation failure reporting** (lines 220-246): Post rejection message on failed validation
4. **Checkout** (lines 248-253): Checkout exact SHA from PR HEAD
5. **Metadata capture** (lines 257-271): Timestamp, deployment ID, commit SHA
6. **Duplicate detection** (lines 276-305): Check if same SHA already running
7. **Already-deployed notification** (lines 309-349): Post skip message if duplicate
8. **Staging deployment** (lines 354-451): Build image, run container, health check
9. **Production pre-check** (lines 472-495): Verify staging image exists (enforce staging-first)
10. **Production deployment** (lines 500-590): Reuse staging image, run container, health check
11. **Status reporting** (lines 594-664): Post success/failure comment with details
12. **Deployment status update** (lines 670-716): Update GitHub Deployment record with final status

**What this workflow does NOT contain:**

- Database migration execution
- Artifact registry push/pull (images stored locally on runner)
- Health check SHA verification (checks `GET /` responds, doesn't verify returned SHA)
- Rollback trigger independent of PRs
- Deployment queueing (uses cancel-in-progress which can abort mid-operation)
- Secrets injection from vault/SSM
- Post-deployment smoke tests beyond HTTP 200 check
- Notification to Slack/email/PagerDuty
- Deployment lock acquisition (beyond GitHub concurrency group)
- Blue-green or canary deployment strategy
- Automated rollback on failed health checks

**Deployment Visibility:**

This workflow creates GitHub Deployment records via API to track deployments correctly:
- Deployments are tied to the PR head SHA (not main branch)
- Visible in GitHub UI: Repository → Environments → staging/production
- Each deployment shows: commit SHA, status, environment URL, workflow logs (PR branch info in description/payload)
- Note: Two deployment records are created (one from job-level `environment:` for approval gates, one from API for correct ref tracking)

---

## Prerequisites

### 1. Self-Hosted Runner

**Required** because workflow deploys to local Docker containers.

Setup:
```bash
# On your deployment machine
cd /path/to/runner
./config.sh --url https://github.com/your-org/your-repo --token YOUR_TOKEN
./run.sh
```

Runner must have:
- Docker installed and running
- Ports 8001 and 8002 available
- Network access to GitHub API
- Sufficient disk space for Docker images

### 2. Docker

```bash
# Verify Docker is running
docker ps

# Ensure ports are not in use
lsof -i :8001
lsof -i :8002
```

### 3. GitHub Environment Protection (for production)

**Setup production environment:**

1. Go to repository Settings → Environments
2. Click "New environment"
3. Name: `production`
4. Enable "Required reviewers"
5. Add at least 1 reviewer (e.g., ktamvada-cyber)
6. (Optional) Enable "Prevent self-review"
7. Save

**Setup staging environment (optional, for deployment history tracking):**

1. Create environment: `staging`
2. Do NOT add protection rules (staging should auto-deploy)

### 4. GitHub Permissions

Workflow requires:
- `contents: read` - Checkout code
- `pull-requests: write` - Read PR metadata via API (issue_comment context limitation)
- `issues: write` - Post deployment status comments
- `deployments: write` - Create GitHub Deployment records via API for correct ref tracking

These are declared in workflow lines 16-20.

### 5. Authorized Users

Edit lines 73-81 in workflow YAML to set allowed deployers:

```javascript
const stagingAuthorizedUsers = [
  'ktamvada-cyber',  // your GitHub username
  'gromag'
];

const productionAuthorizedUsers = [
  'ktamvada-cyber',
  'gromag'
];
```

---

## How to Use

### Staging Deployment

1. **Create or navigate to an open PR**
2. **Ensure PR is in clean state:**
   - No merge conflicts
   - All required checks passing (if any)
   - mergeable_state is "clean"
3. **Comment on the PR:**
   ```
   [staging]
   ```
   (Must be exact; case-sensitive; no extra spaces)
4. **Workflow triggers automatically:**
   - Check Actions tab: Repository → Actions → "Deploy on Comment"
   - Watch workflow progress
5. **Expected outcomes:**
   - **Success:** Bot posts comment with deployment details, URL http://localhost:8001/, SHA, timestamp
   - **Failure:** Bot posts error message (authorization failed, validation failed, build error)
   - **Already deployed:** Bot posts "Deployment Skipped" message
6. **Test staging:**
   ```bash
   curl http://localhost:8001/
   # Expected: {"message":"Hello from CI Demo","commit":"<SHA>","environment":"staging"}

   curl http://localhost:8001/deployment-info
   # Returns full deployment metadata
   ```

### Production Deployment

1. **Deploy to staging first** (see above)
2. **Test staging thoroughly**
3. **Comment on the PR:**
   ```
   [prod]
   ```
4. **Workflow pauses at approval gate:**
   - Navigate to Actions tab → Click workflow run
   - Yellow banner appears: "Review deployments"
   - Click "Review deployments" button
   - Select "production" environment
   - Click "Approve and deploy"
5. **Workflow proceeds after approval:**
   - Verifies staging image exists (FAILS if not)
   - Deploys staging image to production (no rebuild)
6. **Expected outcome:**
   - Bot posts success comment with URL http://localhost:8002/
7. **Test production:**
   ```bash
   curl http://localhost:8002/
   # Expected: {"message":"Hello from CI Demo","commit":"<SHA>","environment":"production"}
   ```

---

## Security Model

### issue_comment Trigger (Default Branch Execution)

**Why it matters:**

GitHub always executes `issue_comment` workflows from the **default branch** (main), even if comment is on PR from feature branch.

**Attack prevented:**

1. Attacker creates PR with modified `.github/workflows/deploy.yml`:
   ```yaml
   # Malicious change: remove authorization check
   if (!authorizedUsers.includes(commenter)) {
     // core.setFailed(errorMsg);  // commented out
   }
   ```
2. Attacker comments `[prod]` on their own PR
3. **Without default-branch execution:** Malicious workflow runs, bypasses auth, deploys attacker code
4. **With default-branch execution:** GitHub ignores feature branch workflow, runs main branch version with auth intact

**Reference:** [GitHub Docs - issue_comment trigger](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#issue_comment)

### SHA-Based Deployment

**Prevents hitchhiker commits:**

Traditional branch-based deployment:
```yaml
# INSECURE
- uses: actions/checkout@v4
  with:
    ref: ${{ pr.head.ref }}  # BAD: uses branch name
```

**Attack scenario:**
1. Attacker creates PR with benign commit A
2. Maintainer reviews commit A, approves
3. **Before deployment:** Attacker pushes malicious commit B to same branch
4. Maintainer triggers deployment (thinks they're deploying A)
5. Workflow checks out branch → gets commit B → deploys malicious code

**This workflow's mitigation (lines 135-151, 201-206):**
```yaml
# SECURE
- uses: actions/checkout@v4
  with:
    ref: ${{ steps.validate.outputs.pr_sha }}  # GOOD: exact SHA
```

SHA is captured at comment time (line 150: `const prSha = pr.head.sha`). Even if branch is updated after comment, workflow deploys the exact SHA that existed when comment was posted.

### Authorization Allowlists

Per-environment user allowlists (lines 73-86):
- **Staging:** ktamvada-cyber, gromag
- **Production:** ktamvada-cyber, gromag

Violations post comment like:
```
❌ AUTHORIZATION FAILED: User "attacker" is not authorized to deploy to production.
Authorized users: ktamvada-cyber, gromag
```

### Validation Checks

Four pre-deployment checks (lines 104-133):
1. **PR is open:** Prevents deploying merged/closed PRs
2. **mergeable_state is "clean":** Ensures all checks pass, no conflicts, not behind base branch
3. **mergeable is not false:** Double-check for merge conflicts
4. **Authorized user:** Per-environment allowlist

All failures post rejection comment to PR.

### Least-Privilege Permissions

Workflow declares minimal permissions (lines 16-19):
- `contents: read` (not write)
- `pull-requests: write` (only to read PR metadata; cannot merge)
- `issues: write` (only to post comments)

Cannot:
- Push code
- Merge PRs
- Modify repository settings
- Access secrets outside workflow scope

---

## Concurrency Model

Configuration (lines 24-26):
```yaml
concurrency:
  group: deployment
  cancel-in-progress: true
```

**Behavior:**

- **One deployment at a time** across all environments
- If deployment A is running and deployment B is triggered:
  1. Deployment A is **cancelled immediately**
  2. Deployment B starts
- Applies globally: staging and production share the same concurrency group

**Risks:**

**Scenario: Mid-teardown cancellation**
1. User comments `[staging]` → Deployment A starts
2. Deployment A reaches line 325: `docker stop myapp-staging`
3. **Before line 327 completes** (`docker rm myapp-staging`), user comments `[prod]` → Deployment B starts
4. Deployment A is cancelled mid-teardown
5. Container might be stopped but not removed
6. Deployment B might encounter name conflict if deploying to same environment

**Current mitigation:** Both stop and rm use `|| true` (lines 325, 327), so partial teardown doesn't fail next deployment.

**Recommended improvement:** See docs/todos.md for safer queueing strategy.

**When cancel-in-progress is beneficial:**
- User fat-fingers and triggers wrong environment → can immediately trigger correct one
- Long-running approval wait → can cancel and redeploy if new changes pushed

**When it's problematic:**
- Concurrent staging and production deployments → production deployment cancels staging mid-flight
- Rapid comment spam → leaves containers in inconsistent states

---

## Environment Protection

**GitHub Environments:** Staging and production are declared dynamically (lines 37-39):

```yaml
environment:
  name: ${{ github.event.comment.body == '[prod]' && 'production' || 'staging' }}
  url: ${{ github.event.comment.body == '[prod]' && 'http://localhost:8002' || 'http://localhost:8001' }}
```

**Protection rules applied:**

- **Staging:** No protection → auto-deploys after validation
- **Production:** Required reviewers (configured in GitHub Settings → Environments)

**Approval flow:**

1. User comments `[prod]`
2. Workflow validates PR (authorization, conflicts, etc.)
3. Workflow reaches `environment: production` (line 38)
4. **GitHub pauses workflow execution**
5. GitHub sends email/notification to required reviewers
6. Reviewer navigates to Actions tab → workflow run
7. Yellow banner: "Review deployments"
8. Reviewer clicks "Review deployments" → selects "production" → clicks "Approve and deploy"
9. Workflow resumes, proceeds with deployment

**Timeout:** Workflow has 15-minute timeout (line 43), **including** approval wait time. If approval takes >15 minutes, workflow fails with timeout error.

**Who can approve:**
- Users configured in Settings → Environments → production → Required reviewers
- Typically: QA lead, tech lead, release manager

**What approver sees:**
- Environment name: production
- URL: http://localhost:8002
- Commit SHA being deployed
- Workflow run link

---

## Output and Observability

### PR Comments Posted

**1. Validation failure:**
```markdown
### ❌ Deployment Rejected

**Error Details:**

❌ AUTHORIZATION FAILED: User "bob" is not authorized to deploy to production.
Authorized users: ktamvada-cyber, gromag

---
📋 **View Full Logs:** [Workflow Run #123](https://github.com/...)
```

**2. Already deployed (skip):**
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
💡 **Note:** No deployment needed - skipping to avoid unnecessary downtime.
```

**3. Deployment success:**
```markdown
### ✅ Deployment SUCCEEDED

#### 📋 Deployment Details
| Field | Value |
|-------|-------|
| **Environment** | `production` |
| **Status** | SUCCEEDED |
| **Commit SHA** | `abc123...` |
| **Build Timestamp** | `2024-02-24T10:30:00Z` |
| **Deployment ID** | `987654` |
| **Container** | `myapp-prod` |
| **Port** | `8002` |
| **Image Digest** | `sha256:def456...` |
| **Service Status** | ✅ Healthy (verified) |

---
#### 🌐 Access Information
**URL:** http://localhost:8002/
**Workflow Run:** [View Logs](https://github.com/...)
```

**4. Deployment failure:**
```markdown
### ❌ Deployment FAILED

#### 📋 Deployment Details
| Field | Value |
|-------|-------|
| **Environment** | `staging` |
| **Status** | FAILED |
| **Service Status** | ❌ Failed |

---
#### ⚠️ Action Required
Check workflow logs for detailed error information.
**Workflow Run:** [View Logs](https://github.com/...)
```

### Workflow Logs

**Access:** Repository → Actions → "Deploy on Comment" → Click specific run

**Key log sections:**

1. **Validate deployment trigger and permissions:** Shows all validation checks, extracted SHA, authorization result
2. **Create GitHub Deployment:** Deployment record creation confirmation
3. **Checkout PR HEAD commit:** Confirms exact SHA checked out
4. **Deploy to Staging/Production:** Docker build output, container start, health check attempts
5. **Post Deployment Status:** Comment posting confirmation
6. **Update Deployment Status:** Final deployment status update

**Debugging failed deployments:**

```bash
# On runner machine
docker ps -a  # Check container status
docker logs myapp-staging  # View application logs
docker inspect myapp-staging  # Check configuration
docker images | grep ci-demo  # List built images
```

### GitHub Deployments UI

**Access:** Repository → Environments → staging or production

**What you'll see:**
- All deployments for each environment
- Each deployment shows:
  - **Ref:** PR head SHA (branch info available in deployment description/payload)
  - **Commit SHA:** Exact PR head commit
  - **Status:** In progress, Success, or Failure
  - **Environment URL:** http://localhost:8001 (staging) or http://localhost:8002 (production)
  - **Workflow logs:** Link to Actions run
- Deployment timeline and history

**Note:** Each deployment creates two records:
1. **Job-level environment (for approval):** Shows main branch, handles GitHub Environment protection
2. **API-created (for tracking):** Shows PR branch/SHA, provides accurate deployment visibility

---

## FAQ and Troubleshooting

### Q: Deployment rejected with "mergeable_state is 'blocked'"

**Cause:** Required status checks are failing or not yet complete.

**Solution:**
1. Check PR → "Checks" tab
2. Wait for all required checks to pass
3. Refresh PR page (GitHub may need to recalculate mergeable_state)
4. Comment `[staging]` again

---

### Q: Deployment rejected with "mergeable_state is 'behind'"

**Cause:** PR branch is behind base branch (main).

**Solution:**
```bash
git checkout your-feature-branch
git merge main  # or git rebase main
git push
```
Wait for checks to pass, then comment `[staging]` again.

---

### Q: Deployment rejected with "mergeable_state is 'unknown'"

**Cause:** GitHub hasn't calculated mergeable state yet (happens on newly opened PRs).

**Solution:**
1. Wait 30-60 seconds
2. Refresh PR page
3. Try commenting `[staging]` again

---

### Q: Production deployment fails with "Staging image does not exist"

**Cause:** Trying to deploy to production without deploying to staging first.

**Solution:**
1. Comment `[staging]` on the PR
2. Wait for staging deployment to succeed
3. Test staging: `curl http://localhost:8001/`
4. Comment `[prod]` on the PR

**Why this happens:** Production MUST reuse the staging image (line 406-448). This enforces the "test in staging first" workflow and ensures production deploys the exact tested artifact.

---

### Q: "docker: Error response from daemon: Conflict. The container name ... is already in use"

**Cause:** Previous deployment failed mid-teardown; container still exists.

**Solution:**
```bash
# On runner machine
docker stop myapp-staging
docker rm myapp-staging
```
Then comment `[staging]` again.

**Why this happens:** If workflow is cancelled mid-deployment (e.g., via cancel-in-progress), container may be created but workflow never cleans it up.

---

### Q: "bind: address already in use" when starting container

**Cause:** Port 8001 or 8002 is occupied by another process.

**Solution:**
```bash
# Find process using port
lsof -i :8001
# Kill it or use different port
kill -9 <PID>

# Or clean up old containers
docker stop myapp-staging
docker rm myapp-staging
```

---

### Q: Health check shows "running_unverified" instead of "healthy"

**Cause:** Container started, but HTTP endpoint didn't respond within 20 seconds (10 retries × 2 seconds, lines 377-396).

**Possible reasons:**
- Application startup is slow (loading data, warming caches)
- Application crashed after container started
- Port mapping is incorrect
- Application is listening on 127.0.0.1 instead of 0.0.0.0

**Debug:**
```bash
docker logs myapp-staging  # Check application startup logs
docker exec -it myapp-staging curl localhost:8000/  # Test from inside container
curl http://localhost:8001/  # Test from host
```

**Implications:** Deployment succeeds (doesn't fail), but service may not be actually serving traffic.

---

## Next Steps

1. **Read detailed scenarios:** [docs/scenarios.md](docs/scenarios.md)
2. **Understand security model:** [docs/security.md](docs/security.md)
3. **Learn operational procedures:** [docs/operations.md](docs/operations.md)
4. **Review TODOs and improvements:** [docs/todos.md](docs/todos.md)
5. **Reference terminology:** [docs/glossary.md](docs/glossary.md)

---

## Quick Reference

### Commands

```bash
# Trigger staging deployment
[staging]

# Trigger production deployment
[prod]

# Check running containers
docker ps

# View application logs
docker logs myapp-staging
docker logs myapp-prod

# Test staging
curl http://localhost:8001/
curl http://localhost:8001/deployment-info

# Test production
curl http://localhost:8002/
curl http://localhost:8002/deployment-info

# Clean up
docker stop myapp-staging myapp-prod
docker rm myapp-staging myapp-prod
docker system prune -a
```

### Ports

- **Staging:** localhost:8001 → container port 8000
- **Production:** localhost:8002 → container port 8000

### Container Names

- **Staging:** `myapp-staging`
- **Production:** `myapp-prod`

### Image Naming

- **Format:** `ci-demo:<COMMIT_SHA>`
- **Example:** `ci-demo:abc123def456...` (full 40-char SHA)

### Environment URLs (as shown in GitHub Environments)

- **Staging:** http://localhost:8001
- **Production:** http://localhost:8002
