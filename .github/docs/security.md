# Security Model and Threat Mitigation

---

## Threat Model

### Assets

- **Production environment** (localhost:8002, myapp-prod container)
- **Staging environment** (localhost:8001, myapp-staging container)
- **Docker images** (ci-demo:<SHA> tagged images)
- **Source code** (repository contents)
- **Secrets** (environment variables, if any)

### Threat Actors

1. **External attacker** (no repository access)
   - Cannot comment on PRs
   - Cannot trigger workflow
   - Threat: Social engineering, compromised accounts

2. **Internal attacker** (has repository read access, can create PRs)
   - Can create malicious PRs
   - Can comment on own PRs
   - Cannot modify main branch directly (assuming branch protection)
   - Threat: Hijack deployment via PR comments

3. **Compromised dependency** (supply chain attack)
   - Malicious npm/pip/apt package
   - Compromised base Docker image
   - Threat: Code injection during build

4. **Insider threat** (authorized deployer)
   - Has deployment privileges
   - Could intentionally deploy malicious code
   - Threat: Rogue deployment, data exfiltration

---

## Mitigations

### 1. Default Branch Workflow Execution

**Threat:** Attacker modifies workflow in feature branch to bypass security checks.

**Attack vector:**
```yaml
# Attacker's PR includes modified .github/workflows/deploy.yml
const authorizedUsers = [...];
# Bypassed:
# if (!authorizedUsers.includes(commenter)) { ... }

# Or:
timeout-minutes: 999999  # Never timeout
```

**Mitigation:**

`issue_comment` trigger **always executes from default branch** (main), documented in workflow lines 3-9:

```yaml
# This workflow uses issue_comment trigger which ALWAYS runs from the default branch (main).
# Even if a malicious PR contains a modified .github/workflows/deploy.yml, GitHub will ignore it
# and execute the version from the default branch only.
```

**Why it works:**
- GitHub ignores workflow files in feature branches for `issue_comment` events
- Only default branch (main) workflow is executed
- Attacker cannot tamper with authorization logic, validation checks, or any workflow behavior

**Reference:** [GitHub Docs](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#issue_comment)

**Verification:**
1. Create PR with modified workflow (add `echo "PWNED"` to validation step)
2. Comment `[staging]` on PR
3. Check workflow logs → no "PWNED" output
4. Workflow runs from main branch, not PR branch

---

### 2. SHA-Based Deployment (Prevents Hitchhiker Commits)

**Threat:** Attacker adds malicious commits to PR after approval but before deployment.

**Attack timeline:**
1. **10:00** — Attacker creates PR with commit A (benign code)
2. **10:30** — Maintainer reviews commit A, approves
3. **10:45** — Maintainer comments `[staging]` to deploy
4. **10:46** — Attacker pushes commit B (malicious code) to same branch
5. **10:47** — Deployment completes

**Question:** Did staging deploy commit A (benign) or commit B (malicious)?

**Insecure approach (branch-based):**
```yaml
# INSECURE
- uses: actions/checkout@v4
  with:
    ref: ${{ pr.head.ref }}  # Uses branch name, e.g., "feature-x"
```
→ Checks out latest commit on branch = commit B 🚨

**Secure approach (SHA-based, THIS WORKFLOW):**
```yaml
# SECURE (lines 201-206)
- uses: actions/checkout@v4
  with:
    ref: ${{ steps.validate.outputs.pr_sha }}  # Uses exact SHA
```

**How it works:**

Validation step (line 150) captures SHA **at comment time**:
```javascript
const prSha = pr.head.sha;  // Captures SHA at 10:45
```

Even if branch is updated at 10:46, workflow deploys the SHA that existed at 10:45 (commit A).

**Verification:**
```bash
# In workflow logs
echo "Target commit SHA: abc123..."  # Line 151

# In deployed container
curl http://localhost:8001/
# {"commit":"abc123..."}  ← Matches logged SHA
```

**Limitations:**
- Doesn't prevent attacker from updating PR **before** comment
- Reviewer must verify commit SHA before commenting `[staging]` or `[prod]`

---

### 3. Authorization Allowlists (Per-Environment)

**Threat:** Unauthorized user triggers deployment.

**Attack vector:**
- Attacker (with read access) creates PR
- Comments `[prod]` on own PR

**Mitigation:**

Per-environment user allowlists (lines 73-86):

```javascript
const stagingAuthorizedUsers = [
  'ktamvada-cyber',
  'gromag'
];

const productionAuthorizedUsers = [
  'ktamvada-cyber',
  'gromag'
];

const authorizedUsers = environment === 'staging'
  ? stagingAuthorizedUsers
  : productionAuthorizedUsers;

if (!authorizedUsers.includes(commenter)) {
  core.setFailed(...);  // Deployment rejected
}
```

**Enforcement:**
- Validation step (lines 68-95) checks commenter against allowlist
- Failure posts rejection comment and fails workflow
- No checkout, build, or deployment occurs

**Verification:**
1. User not in list comments `[prod]`
2. Workflow logs: `❌ AUTHORIZATION FAILED: User "alice"...`
3. PR comment: `❌ Deployment Rejected ... Authorized users: ktamvada-cyber, gromag`

**Limitations:**
- Hardcoded in YAML (requires code change to add/remove users)
- No role-based access control (RBAC)
- No integration with external identity providers (LDAP, Okta, etc.)

**Recommended improvement:** See docs/todos.md — use GitHub Teams or external allowlist file

---

### 4. PR Validation (Prevents Deploying Broken/Conflicted PRs)

**Threat:** Deploying PR with merge conflicts, failing checks, or closed state.

**Attack vector:**
- PR has conflicts with main
- Attacker comments `[staging]`
- Deployment succeeds but merges conflicted code

**Mitigations:**

Four validation checks (lines 104-133):

**Check 1: PR is open (lines 104-112)**
```javascript
if (pr.state !== 'open') {
  core.setFailed(`PR #${context.issue.number} is not open (state: ${pr.state})`);
}
```
→ Prevents deploying closed or merged PRs

**Check 2: mergeable_state is "clean" (lines 114-123)**
```javascript
if (pr.mergeable_state !== 'clean') {
  core.setFailed(`mergeable_state is "${pr.mergeable_state}". Required: "clean"`);
}
```
→ Ensures:
- All required status checks passed
- No merge conflicts
- Not behind base branch
- Not in "unknown", "blocked", "dirty", "unstable" states

**Check 3: No merge conflicts (lines 125-133)**
```javascript
if (pr.mergeable === false) {
  core.setFailed(`PR #${context.issue.number} has merge conflicts`);
}
```
→ Double-check for conflicts (mergeable_state should catch this, but explicit is safer)

**Why multiple checks:**
- GitHub's `mergeable_state` calculation is asynchronous (can be "unknown" immediately after PR creation)
- `mergeable` is a direct conflict check (true/false/null)
- Layered validation reduces false negatives

**Verification:**
```bash
# Create PR with conflicts
git checkout feature-x
# Modify file that conflicts with main
git push

# Comment [staging] on PR
# Workflow fails:
# ❌ VALIDATION FAILED: PR #42 mergeable_state is "dirty". Required: "clean".
```

---

### 5. Least-Privilege Permissions

**Threat:** Compromised workflow could modify repository, merge PRs, access secrets beyond scope.

**Mitigation:**

Explicit permissions declaration (lines 16-19):

```yaml
permissions:
  contents: read        # Can only read code; cannot push
  pull-requests: write  # Can read PR metadata; cannot merge
  issues: write         # Can post comments; cannot close/transfer
```

**What workflow CANNOT do:**
- Push commits to any branch
- Merge pull requests
- Modify repository settings
- Create/delete branches
- Access secrets not explicitly declared in workflow
- Create releases
- Modify GitHub Actions settings

**What workflow CAN do:**
- Read repository files (for checkout)
- Read PR metadata (number, SHA, state, mergeable_state)
- Post comments on PRs
- Post comments on issues

**Why `pull-requests: write` instead of `read`:**

GitHub API quirk: `issue_comment` events provide issue context, not PR context. To get PR metadata (`pr.head.sha`, `pr.mergeable_state`), workflow must call:
```javascript
await github.rest.pulls.get({ owner, repo, pull_number })
```
This endpoint requires `pull-requests: write` permission (despite being a read operation).

**Verification:**
```bash
# In workflow, try to merge PR
await github.rest.pulls.merge({ owner, repo, pull_number })
# Result: Error 403 Forbidden (missing 'contents: write' permission)
```

---

### 6. Staging-First Enforcement (Prevents Untested Production Deployments)

**Threat:** Deploying to production without testing in staging.

**Attack vector:**
- Attacker comments `[prod]` directly
- Skips staging testing
- Deploys untested code to production

**Mitigation:**

Production pre-check (lines 406-448):

```yaml
- name: Verify Staging Image Exists
  if: environment == 'production'
  run: |
    if ! docker image inspect ci-demo:${COMMIT_SHA} >/dev/null 2>&1; then
      echo "❌ DEPLOYMENT FAILED"
      echo "Staging image does not exist: ci-demo:${COMMIT_SHA}"
      exit 1
    fi
```

**How it works:**
1. User comments `[prod]`
2. Workflow checks if `ci-demo:<SHA>` image exists locally
3. If not found → **deployment fails** with clear message
4. If found → deployment proceeds (reuses staging image)

**Why it matters:**
- Forces "deploy to staging → test → deploy to production" workflow
- Production deploys **exact same Docker image** that was tested in staging
- No rebuilds in production (prevents supply chain attacks between staging and production builds)

**Supply chain attack prevented:**

**Scenario:**
1. **10:00** — Deploy to staging → builds image with clean npm package `foo@1.0.0`
2. **10:30** — Test staging, looks good
3. **11:00** — Comment `[prod]`
4. **Between 10:00 and 11:00:** npm package `foo@1.0.0` was compromised (attacker published malicious version with same version number)
5. **With rebuild in production:** `docker build` pulls compromised `foo@1.0.0` → production has malicious code
6. **With image reuse (this workflow):** Production uses staging image (built at 10:00) → production has clean `foo@1.0.0`

**Compliance benefit:**
- SOC 2, PCI-DSS, HIPAA require deploying exact tested artifact
- Rebuilding in production violates "what you test is what you deploy" principle

**Verification:**
```bash
# Delete staging image
docker rmi ci-demo:abc123...

# Comment [prod]
# Workflow fails:
# ❌ DEPLOYMENT FAILED
# Staging image does not exist: ci-demo:abc123...
```

---

### 7. Environment Protection (Manual Approval for Production)

**Threat:** Accidental or unauthorized production deployment.

**Mitigation:**

GitHub Environment protection (lines 37-39):

```yaml
environment:
  name: ${{ github.event.comment.body == '[prod]' && 'production' || 'staging' }}
```

**Configuration (in GitHub UI):**
- Settings → Environments → production
- Required reviewers: 1+ designated approvers
- Optional: Prevent self-review (deployer cannot approve own deployment)

**How it works:**
1. User comments `[prod]`
2. Workflow validates PR
3. Workflow reaches `environment: production` line
4. **GitHub pauses workflow**
5. GitHub notifies required reviewers
6. Reviewer must manually click "Approve and deploy"
7. Workflow resumes only after approval

**Benefits:**
- **Two-person rule:** Deployer and approver are different people (if "prevent self-review" enabled)
- **Audit trail:** GitHub logs who approved, when, for which commit
- **Emergency brake:** Reviewer can reject if they notice issues

**Verification:**
```bash
# Comment [prod]
# Actions tab shows: "⏸️ Waiting for review: production needs approval"

# As reviewer, click "Review deployments" → "Approve"
# Workflow resumes
```

**Limitations:**
- Approval is per-workflow-run, not per-commit (approver might not verify exact SHA)
- No automated verification of "what are you approving" (approver must check manually)

**Recommended improvement:** See docs/todos.md — display commit SHA and diff in approval UI

---

## Security Checklist

**Before deploying:**

- [ ] Self-hosted runner is running on trusted machine
- [ ] Runner has Docker installed and accessible
- [ ] Ports 8001 and 8002 are not exposed to public internet
- [ ] GitHub Environment "production" is configured with required reviewers
- [ ] Authorized user lists (lines 73-81) contain only trusted users
- [ ] Repository has branch protection on main (prevents direct pushes, requires PR reviews)
- [ ] Dockerfile does not include secrets (use GitHub Secrets or runtime env vars)
- [ ] Application does not log sensitive data (commit SHA, deployment ID are safe to log)

**During deployment:**

- [ ] Verify PR number matches intended PR
- [ ] Verify commit SHA matches reviewed code (check PR → Commits tab)
- [ ] Ensure mergeable_state is "clean" (not "dirty", "unknown", "blocked")
- [ ] For production: Verify staging has been tested

**After deployment:**

- [ ] Check deployment status comment for success
- [ ] Verify container is running: `docker ps | grep myapp-{environment}`
- [ ] Test service: `curl http://localhost:{port}/deployment-info`
- [ ] Verify returned commit SHA matches deployed SHA
- [ ] Check application logs for errors: `docker logs myapp-{environment}`

---

## Known Limitations

1. **SHA verification in health check:** Workflow checks if `GET /` responds (HTTP 200) but does not verify returned commit SHA matches deployed SHA. Application could serve wrong version or lie about deployed SHA.

2. **No secrets management:** Workflow does not inject secrets from vault, AWS SSM, etc. Secrets must be hardcoded in Dockerfile or passed as GitHub Secrets.

3. **Single-runner deployment:** Images stored locally on runner. If runner changes, images are lost. No registry push/pull for multi-runner support.

4. **Approval UI shows minimal context:** Production approver sees environment name and URL, but not commit SHA or diff. Must manually check PR to know what they're approving.

5. **No deployment lock beyond concurrency group:** `cancel-in-progress` can abort mid-deployment. No persistent lock to prevent concurrent deployments.

6. **Hardcoded user allowlists:** Adding/removing deployers requires code change to main branch.

See docs/todos.md for recommended improvements.
