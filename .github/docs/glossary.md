# Glossary

---

## A

**Already Deployed**
Status when workflow detects target commit SHA is already running in target environment. Deployment is skipped to avoid unnecessary downtime. See: Duplicate detection.

**Approval Gate**
Point in workflow where execution pauses, waiting for designated reviewers to manually approve before proceeding. Used for production deployments via GitHub Environment protection.

**Authorized User**
User whose GitHub username is listed in workflow's allowlist for specific environment. Only authorized users can trigger deployments via PR comments.

---

## B

**Build Args**
Docker build arguments passed to `docker build --build-arg KEY=VALUE`. Used to bake metadata (COMMIT_SHA, BUILD_TIMESTAMP) into image at build time.

**Build Metadata**
Deployment information captured at workflow start: build timestamp (ISO 8601), deployment ID (GitHub run ID), commit SHA. Used for tracking and observability.

---

## C

**Cancel-in-Progress**
Concurrency control setting (`cancel-in-progress: true`) that aborts running workflows when new workflow with same concurrency group starts. Can cause mid-operation cancellations.

**Checkout**
Git operation to retrieve specific commit from repository. Workflow uses `actions/checkout@v4` with explicit SHA (not branch name) to prevent hitchhiker attacks.

**Clean (mergeable_state)**
GitHub PR state indicating: no merge conflicts, all required checks passed, not behind base branch, ready to merge. Required for deployment validation.

**Commit SHA**
40-character hexadecimal Git commit identifier (e.g., `abc123def456...`). Used as Docker image tag and deployment identifier. Ensures deploying exact code version.

**Concurrency Group**
Named group (`group: deployment`) that limits number of concurrent workflow runs. Only one workflow per group runs at a time; others are queued or cancelled.

---

## D

**Default Branch**
Repository's main branch (usually `main` or `master`). `issue_comment` workflows always execute from default branch, even if comment is on PR from feature branch.

**Deployment ID**
Unique identifier for deployment run. Uses GitHub's workflow run ID (`github.run_id`). Different for each workflow execution, even if deploying same commit SHA.

**Digest (Image Digest)**
SHA256 hash of Docker image contents (e.g., `sha256:def456...`). Immutable identifier; two images with same digest are byte-for-byte identical. Used to verify image integrity.

**Duplicate Detection**
Workflow step that checks if target commit SHA is already running in target environment. Prevents redundant redeployments.

---

## E

**Environment (GitHub Environment)**
GitHub feature for deployment protection and tracking. Supports required reviewers, wait timers, deployment branches. Used to gate production deployments.

**Environment (Deployment Environment)**
Target runtime environment for deployment. Two values: `staging` (localhost:8001) or `production` (localhost:8002).

---

## H

**Health Check**
Workflow step that verifies deployed service is responding. Uses `curl` to test HTTP endpoint. Retry logic allows for slow application startup.

**Healthy**
Health check status indicating service responds to HTTP requests within timeout. Workflow posts "✅ Healthy (verified)" in deployment comment.

**Hitchhiker Commit**
Attack where malicious commit is added to PR branch after approval but before deployment. SHA-based deployment prevents this by deploying exact commit at comment time, not branch tip.

---

## I

**Image Immutability**
Principle that production must deploy exact same Docker image tested in staging, without rebuilding. Prevents supply chain attacks and ensures "what you test is what you deploy."

**issue_comment Trigger**
GitHub Actions event that fires when comment is created on issue or PR. Always executes workflow from default branch, preventing feature branch tampering.

---

## M

**Mergeable**
GitHub PR property indicating whether PR can be merged without conflicts. Values: `true` (no conflicts), `false` (conflicts exist), `null` (unknown/calculating).

**mergeable_state**
GitHub PR property indicating overall merge readiness. Values: `clean` (ready), `dirty` (conflicts), `blocked` (checks failing), `behind` (outdated), `unstable`, `unknown`.

**Metadata (Build Metadata)**
See: Build Metadata.

---

## P

**PR (Pull Request)**
GitHub feature for proposing code changes. Workflow triggers on PR comments, deploys PR HEAD commit.

**Production**
Live environment serving real users. Localhost:8002, container `myapp-prod`. Requires manual approval via GitHub Environment protection.

---

## R

**Readiness Status**
Workflow output indicating service health after deployment. Values:
- `healthy`: Service responds to HTTP requests
- `running_unverified`: Container running but HTTP endpoint not responding within timeout
- `failed`: Container failed to start

**Required Reviewers**
GitHub Environment protection feature. List of users who must approve deployment before workflow proceeds. Enforces separation of duties (deployer ≠ approver).

**Rollback**
Reverting to previous working version. Workflow has no built-in rollback trigger; must comment on old PR or manually restart old container.

**Running Unverified**
Health check status when container is running but HTTP endpoint doesn't respond within timeout (10 retries × 2 seconds). Deployment succeeds but service may not be serving traffic.

---

## S

**Self-Hosted Runner**
GitHub Actions runner installed on user's own machine (not GitHub-hosted). Required for this workflow to access local Docker daemon.

**SHA (Commit SHA)**
See: Commit SHA.

**SHA-Based Deployment**
Deploying exact commit SHA instead of branch name. Prevents hitchhiker attacks by ensuring deployed code matches validated code, even if branch is updated after validation.

**Staging**
Pre-production testing environment. Localhost:8001, container `myapp-staging`. No approval required; deploys immediately after validation.

**Staging-First**
Workflow requirement that production must reuse staging image. Production deployment fails if staging image doesn't exist, forcing "deploy to staging → test → deploy to production" flow.

---

## T

**Timeout**
Maximum workflow execution time (15 minutes by default, line 43). Includes approval wait time for production. Workflow fails if timeout exceeded.

**Trigger**
Event that starts workflow. This workflow uses `issue_comment` (PR comment creation) with exact match for `[staging]` or `[prod]`.

---

## V

**Validation**
Workflow step (lines 47-167) that performs security and readiness checks before deployment:
- Command match (`[staging]` or `[prod]`)
- User authorization
- PR is open
- mergeable_state is "clean"
- No merge conflicts
- SHA extraction

---

## W

**Workflow**
GitHub Actions automated process defined in `.github/workflows/deploy.yml`. Triggered by PR comments, performs validation, builds/runs Docker containers, posts status.

---

## Example Usage in Context

**"The deployment failed because mergeable_state was dirty, indicating a hitchhiker commit might have introduced conflicts after the SHA-based checkout."**

Translation: The workflow rejected deployment because GitHub detected merge conflicts (mergeable_state: dirty). This could happen if someone pushed conflicting code to the PR branch after the deployer commented. However, even if there were no conflicts, SHA-based deployment would deploy the exact commit at comment time, not any commits pushed afterward (preventing hitchhiker attacks).

**"Production requires a staging-first approach with image immutability to prevent supply chain attacks between builds."**

Translation: You must deploy to staging before production. Production reuses the staging Docker image without rebuilding (image immutability). This prevents a scenario where a malicious package is published between staging build and production build, causing production to get compromised code while staging had clean code.

**"The workflow runs from the default branch via issue_comment trigger, even if an attacker modifies the workflow in their feature branch."**

Translation: When you comment `[staging]` on a PR from a feature branch, GitHub executes the workflow file from the main branch, not the feature branch. This prevents attackers from tampering with workflow logic (like removing authorization checks) in their PR.
