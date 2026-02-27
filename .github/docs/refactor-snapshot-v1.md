# 📸 SYSTEM SNAPSHOT v1 — Pre-Refactor State

**Date:** 2026-02-27
**Purpose:** Complete baseline snapshot before structural refactoring
**Status:** LOCKED — This document must not be modified during refactor

---

## 📂 CURRENT .github DIRECTORY TREE

```
.github/
├── OPS.md
├── README.md
├── REVIEW-SUMMARY.md
├── docs/
│   ├── glossary.md
│   ├── operations.md
│   ├── scenarios.md
│   ├── security.md
│   └── todos.md
└── workflows/
    ├── deploy.yml         (947 lines)
    ├── ops.yml            (1,572 lines)
    └── test-coverage.yml  (132 lines)

TOTAL: 2,651 workflow lines
```

---

## 📋 WORKFLOW: test-coverage.yml

**File:** `.github/workflows/test-coverage.yml`
**Lines:** 132
**Purpose:** Run tests with coverage gate, create GitHub check run

### Triggers
```yaml
on:
  pull_request:
  push:
    branches:
      - '**'
    tags:
      - '**'
  workflow_dispatch:
```

### Permissions
```yaml
permissions:
  contents: read
  checks: write
```

### Concurrency
None

### Environment Protection
None

### Jobs

#### Job: `test-coverage`
- **Name:** `coverage-tests`
- **Runs-on:** `ubuntu-latest`
- **Timeout:** None specified

### Steps

| Step Name | ID | Lines | Type |
|-----------|---|-------|------|
| Checkout code | - | 25-28 | action |
| Set up Python | - | 30-34 | action |
| Install dependencies | - | 36-39 | bash |
| Run tests with coverage | `run_tests` | 41-51 | bash |
| Report coverage summary | `coverage_summary` | 53-69 | bash |
| Create check run with coverage percentage | - | 71-132 | JS |

### Inline JavaScript Blocks

#### Block 1: Lines 73-132 (60 lines)
**Step:** "Create check run with coverage percentage"
**Purpose:** Create GitHub check run with test and coverage results

**Inputs Used:**
- `steps.coverage_summary.outputs.coverage_pct`
- `steps.run_tests.outcome`
- `context.eventName`
- `context.payload.pull_request.head.sha`
- `context.sha`

**Outputs:** None (creates check run via API)

**Key Logic:**
- Determines target SHA based on event type
- Creates check run with name `'test-coverage'`
- Sets conclusion to `success` or `failure`
- Formats title: `${emoji} Coverage ${coveragePct}% (${comparison})`

**API Calls:**
- `github.rest.checks.create()`

### Inline Bash Blocks

#### Block 1: Lines 37-39 (3 lines)
**Step:** "Install dependencies"
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### Block 2: Lines 44-51 (8 lines)
**Step:** "Run tests with coverage"
```bash
pytest --cov=app \
       --cov-report=term-missing \
       --cov-report=json \
       --cov-fail-under=70 \
       -v
```

#### Block 3: Lines 56-69 (14 lines)
**Step:** "Report coverage summary"
**Outputs:**
- `coverage_pct` (GITHUB_OUTPUT)

### Step Outputs

| Step ID | Output Name | Type | Sample Value |
|---------|-------------|------|--------------|
| `run_tests` | (outcome only) | outcome | `success` / `failure` |
| `coverage_summary` | `coverage_pct` | string | `"75.3"` |

---

## 📋 WORKFLOW: deploy.yml

**File:** `.github/workflows/deploy.yml`
**Lines:** 947
**Purpose:** Deploy PR to staging/production on comment trigger

### Triggers
```yaml
on:
  issue_comment:
    types: [created]
```

### Permissions
```yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
  deployments: write
  checks: read
```

### Concurrency
```yaml
concurrency:
  group: deployment
  cancel-in-progress: true
```

### Environment Variables
```yaml
env:
  STAGING_PORT: 8001
  PROD_PORT: 8002
  STAGING_CONTAINER: myapp-staging
  PROD_CONTAINER: myapp-prod
  IMAGE_NAME: ci-demo
  CONTAINER_INTERNAL_PORT: 8000
  HEALTH_CHECK_MAX_RETRIES: 10
  HEALTH_CHECK_RETRY_SLEEP: 2
```

### Environment Protection
```yaml
environment:
  name: ${{ github.event.comment.body == '[prod]' && 'production' || 'staging' }}
  url: ${{ github.event.comment.body == '[prod]' && 'http://localhost:8002' || 'http://localhost:8001' }}
```

### Jobs

#### Job: `validate-and-deploy`
- **Condition:** `github.event.issue.pull_request != null`
- **Runs-on:** `self-hosted`
- **Timeout:** 15 minutes

### Steps

| Step Name | ID | Lines | Type |
|-----------|---|-------|------|
| Validate deployment trigger and permissions | `validate` | 61-225 | JS |
| Create GitHub Deployment | `create_deployment` | 231-280 | JS |
| Verify Coverage Gate | `verify_coverage` | 282-369 | JS |
| Post Coverage Gate Failure | - | 370-422 | JS |
| Post Validation Failure | - | 425-450 | JS |
| Checkout PR HEAD commit | - | 453-460 | action |
| Capture Build Metadata | `build_metadata` | 462-479 | bash |
| Check Already Deployed | `check_deployed` | 481-512 | bash |
| Post Already Deployed Status | - | 514-557 | JS |
| Deploy to Staging | `deploy_staging` | 560-690 | bash |
| Verify Staging Image Exists | - | 692-719 | bash |
| Deploy to Production | `deploy_production` | 721-818 | bash |
| Post Deployment Status | - | 820-893 | JS |
| Update Deployment Status | - | 895-944 | JS |

### Inline JavaScript Blocks

#### Block 1: Lines 63-225 (163 lines)
**Step:** "Validate deployment trigger and permissions"
**ID:** `validate`

**Inputs Used:**
- `context.payload.comment.body`
- `context.payload.comment.user.login`
- `context.issue.number`

**Outputs:**
- `should_deploy` (string: 'true' | undefined)
- `environment` (string: 'staging' | 'production')
- `pr_sha` (string: 40-char hex)
- `pr_number` (number)
- `pr_branch` (string)
- `error_message` (string)

**Hardcoded Values:**
```javascript
const validCommands = ['[staging]', '[prod]'];
const stagingAuthorizedUsers = ['ktamvada-cyber', 'gromag'];
const productionAuthorizedUsers = ['ktamvada-cyber', 'gromag'];
```

**API Calls:**
- `github.rest.pulls.get()`
- `github.rest.checks.listForRef()` (for coverage gate check)

**Key Logic:**
- Strict command matching: `['[staging]', '[prod]']`
- Authorization check (different users per environment)
- PR state validation (must be `'open'`)
- Mergeable state validation (must be `'clean'`)
- Merge conflict check (`mergeable === false`)
- Coverage check detection and error extraction
- SHA extraction from PR head

**Failure Conditions:**
- Invalid command
- Unauthorized user
- PR not open
- PR not mergeable
- Coverage check failed

#### Block 2: Lines 234-280 (47 lines)
**Step:** "Create GitHub Deployment"
**ID:** `create_deployment`

**Condition:** `steps.validate.outputs.should_deploy == 'true'`

**Inputs Used:**
- `steps.validate.outputs.environment`
- `steps.validate.outputs.pr_sha`
- `steps.validate.outputs.pr_branch`
- `steps.validate.outputs.pr_number`
- `context.payload.comment.user.login`
- `context.payload.comment.id`

**Outputs:**
- `deployment_id` (number)

**API Calls:**
- `github.rest.repos.createDeployment()`
- `github.rest.repos.createDeploymentStatus()`

**Deployment Payload Structure:**
```javascript
{
  pr_number: prNumber,
  pr_branch: prBranch,
  pr_sha: prSha,
  triggered_by: context.payload.comment.user.login,
  comment_id: context.payload.comment.id
}
```

#### Block 3: Lines 285-369 (85 lines)
**Step:** "Verify Coverage Gate"
**ID:** `verify_coverage`

**Condition:** `steps.validate.outputs.should_deploy == 'true'`

**Inputs Used:**
- `steps.validate.outputs.pr_sha`

**Outputs:**
- `error_message` (string)
- `target_sha` (string)
- `check_url` (string)
- `coverage_pct` (string)
- `coverage_check_url` (string)

**Hardcoded Values:**
```javascript
const requiredCheckName = 'test-coverage';
```

**API Calls:**
- `github.rest.checks.listForRef()`

**Regex Patterns:**
```javascript
/Coverage\s+([\d.]+)%/
```

**Key Logic:**
- Query all check runs for SHA
- Find check named `'test-coverage'`
- Verify conclusion === `'success'`
- Extract coverage percentage from title

**Failure Conditions:**
- Check not found
- Check conclusion !== 'success'

#### Block 4: Lines 372-422 (51 lines)
**Step:** "Post Coverage Gate Failure"

**Condition:** `failure() && steps.verify_coverage.outputs.error_message != ''`

**Inputs Used:**
- `steps.verify_coverage.outputs.error_message`
- `context.issue.number`

**API Calls:**
- `github.rest.issues.createComment()`

#### Block 5: Lines 427-450 (24 lines)
**Step:** "Post Validation Failure"

**Condition:** `failure() && steps.validate.outputs.error_message != ''`

**Inputs Used:**
- `steps.validate.outputs.error_message`
- `context.issue.number`

**API Calls:**
- `github.rest.issues.createComment()`

#### Block 6: Lines 516-557 (42 lines)
**Step:** "Post Already Deployed Status"

**Condition:** `steps.check_deployed.outputs.already_deployed == 'true'`

**Inputs Used:**
- `steps.check_deployed.outputs.deployment_info`
- `context.issue.number`

**API Calls:**
- `github.rest.issues.createComment()`

#### Block 7: Lines 822-893 (72 lines)
**Step:** "Post Deployment Status"

**Condition:** `always() && steps.validate.outputs.should_deploy == 'true'`

**Inputs Used:**
- Job status
- Step outcomes
- Multiple step outputs

**API Calls:**
- `github.rest.issues.createComment()`

#### Block 8: Lines 897-944 (48 lines)
**Step:** "Update Deployment Status"

**Condition:** `always() && steps.create_deployment.outputs.deployment_id`

**Inputs Used:**
- `steps.create_deployment.outputs.deployment_id`
- `steps.validate.outputs.environment`
- Job status

**Outputs:** None

**API Calls:**
- `github.rest.repos.createDeploymentStatus()`

### Inline Bash Blocks

#### Block 1: Lines 465-479 (15 lines)
**Step:** "Capture Build Metadata"
**ID:** `build_metadata`

**Outputs:**
- `build_timestamp` (GITHUB_OUTPUT)

#### Block 2: Lines 487-510 (24 lines)
**Step:** "Determine Container Configuration"
**ID:** Implicit in deployment steps

#### Block 3: Lines 570-690 (121 lines)
**Step:** "Deploy to Staging"
**ID:** `deploy_staging`

**Key Actions:**
- Docker build
- Docker push
- Docker run
- Health check loop

#### Block 4: Lines 696-719 (24 lines)
**Step:** "Verify Staging Image Exists"

#### Block 5: Lines 731-818 (88 lines)
**Step:** "Deploy to Production"
**ID:** `deploy_production`

**Key Actions:**
- Docker pull
- Docker run
- Health check loop

### Step Outputs

| Step ID | Output Name | Type | Used By |
|---------|-------------|------|---------|
| `validate` | `should_deploy` | string | Multiple steps |
| `validate` | `environment` | string | Multiple steps |
| `validate` | `pr_sha` | string | Checkout, Deploy |
| `validate` | `pr_number` | string | Comments |
| `validate` | `pr_branch` | string | Deployment |
| `validate` | `error_message` | string | Error posting |
| `create_deployment` | `deployment_id` | string | Update deployment |
| `verify_coverage` | `error_message` | string | Error posting |
| `verify_coverage` | `target_sha` | string | - |
| `verify_coverage` | `check_url` | string | - |
| `verify_coverage` | `coverage_pct` | string | - |
| `build_metadata` | `build_timestamp` | string | - |
| `check_deployed` | `already_deployed` | string | Condition |
| `check_deployed` | `deployment_info` | string | Comment |

---

## 📋 WORKFLOW: ops.yml

**File:** `.github/workflows/ops.yml`
**Lines:** 1,572
**Purpose:** Ops control plane for restart/redeploy/rollback operations

### Triggers
```yaml
on:
  workflow_dispatch:
    inputs:
      environment: (staging | production)
      action: (restart | redeploy | rollback)
      sha: (optional string)
      steps: (optional string)
      confirm: (optional string)
  issue_comment:
    types: [created]
```

### Permissions
```yaml
permissions:
  contents: read
  issues: write
  deployments: write
  pull-requests: read
  checks: read
```

### Concurrency
```yaml
concurrency:
  group: ops
  cancel-in-progress: true
```

### Environment Variables
```yaml
env:
  OPS_ISSUE_NUMBER: 2
  STAGING_PORT: 8001
  PROD_PORT: 8002
  STAGING_CONTAINER: myapp-staging
  PROD_CONTAINER: myapp-prod
  IMAGE_NAME: ci-demo
  CONTAINER_INTERNAL_PORT: 8000
  HEALTH_CHECK_MAX_RETRIES: 10
  HEALTH_CHECK_RETRY_SLEEP: 2
```

### Environment Protection
```yaml
environment:
  name: ${{ github.event.inputs.environment || (github.event_name == 'issue_comment' && (github.event.comment.body == '[prod-restart]' || startsWith(github.event.comment.body, '[prod-redeploy') || startsWith(github.event.comment.body, '[prod-rollback')) && 'production' || 'staging') }}
  url: (computed based on environment)
```

### Jobs

#### Job: `ops`
- **Runs-on:** `self-hosted`
- **Timeout:** 15 minutes

### Steps

| Step Name | ID | Lines | Type |
|-----------|---|-------|------|
| Validate and Parse Ops Trigger | `validate` | 102-309 | JS |
| Post Validation Failure | - | 313-341 | JS |
| Resolve Ref to SHA | `resolve_sha` | 347-473 | JS |
| Post Ref Resolution Failure | - | 477-510 | JS |
| Determine Current SHA | `determine_current` | 525-555 | bash |
| Compute Rollback Target | `compute_rollback_api` | 561-717 | JS |
| Determine Target SHA | `determine_sha` | 720-898 | bash |
| Verify Coverage Gate | `verify_coverage` | 903-999 | JS |
| Post Coverage Gate Failure | - | 1001-1060 | JS |
| Create GitHub Deployment | `create_deployment` | 1061-1183 | JS |
| Execute Ops Operation | `execute_ops` | 1185-1425 | bash |
| Post Ops Status Comment | - | 1427-1512 | JS |
| Update Deployment Status | - | 1515-1572 | JS |

### Inline JavaScript Blocks

#### Block 1: Lines 104-309 (206 lines)
**Step:** "Validate and Parse Ops Trigger"
**ID:** `validate`

**Inputs Used:**
- `context.eventName`
- `context.payload.comment.body` (if issue_comment)
- `github.event.inputs.*` (if workflow_dispatch)
- `process.env.OPS_ISSUE_NUMBER`

**Outputs:**
- `should_run` (string: 'true' | 'false')
- `action` (string: 'restart' | 'redeploy' | 'rollback')
- `environment` (string: 'staging' | 'production')
- `target_sha` (string)
- `steps` (string)
- `confirm` (string)
- `container_name` (string)
- `port` (string)
- `requester` (string)
- `skip_tagging` (string: 'true')
- `error_message` (string)

**Hardcoded Values:**
```javascript
const opsIssueNumber = Number(process.env.OPS_ISSUE_NUMBER); // 2
const stagingAuthorizedUsers = ['ktamvada-cyber', 'gromag'];
const productionAuthorizedUsers = ['ktamvada-cyber', 'gromag'];
```

**Regex Patterns:**
```javascript
const commandRegex = /^\[(staging|prod)-(restart|redeploy|rollback)(?:\s+sha=([^\s\]]+))?(?:\s+steps=(\d+))?(?:\s+confirm=(yes))?\]$/;
```

**Key Logic:**
- Dual trigger handling (workflow_dispatch vs issue_comment)
- Ops issue number security gate
- Command regex parsing
- Authorization check
- Production confirmation requirement
- Validation: cannot provide both sha and steps

**Failure Conditions:**
- Wrong issue number
- Invalid command syntax
- Unauthorized user
- Production op missing confirm=yes
- Both sha and steps provided
- Rollback missing both sha and steps

#### Block 2: Lines 315-341 (27 lines)
**Step:** "Post Validation Failure"

**Condition:** `failure() && steps.validate.outputs.should_run != 'true'`

**API Calls:**
- `github.rest.issues.createComment()`

#### Block 3: Lines 352-473 (122 lines)
**Step:** "Resolve Ref to SHA"
**ID:** `resolve_sha`

**Condition:** `steps.validate.outputs.should_run == 'true' && steps.validate.outputs.target_sha != ''`

**Inputs Used:**
- `steps.validate.outputs.target_sha`

**Outputs:**
- `resolved_sha` (string: 40-char hex)
- `is_tag` (string: 'true' | 'false')
- `original_ref` (string)
- `ref_type` (string: 'tag' | 'branch' | 'ref' | 'commit')
- `error_message` (string)

**Regex Patterns:**
```javascript
/^[a-f0-9]{40}$/  // Full SHA validation
```

**API Calls:**
- `github.rest.git.getRef()` (multiple strategies)
- `github.rest.git.getTag()` (for annotated tags)
- `github.rest.repos.getCommit()` (fallback)

**Key Logic:**
- 4-strategy resolution:
  1. Already full SHA → return
  2. Try as tag (handle annotated vs lightweight)
  3. Try as branch
  4. Try as raw ref
  5. Try as commit (handles short SHAs)
- Annotated tag dereferencing

**Failure Conditions:**
- All resolution strategies fail
- Resolved SHA invalid format

#### Block 4: Lines 479-510 (32 lines)
**Step:** "Post Ref Resolution Failure"

**Condition:** `failure() && steps.resolve_sha.outputs.error_message != ''`

**API Calls:**
- `github.rest.issues.createComment()`

#### Block 5: Lines 568-717 (150 lines)
**Step:** "Compute Rollback Target (GitHub Deployments API)"
**ID:** `compute_rollback_api`

**Condition:** `steps.validate.outputs.action == 'rollback' && steps.validate.outputs.target_sha == ''`

**Inputs Used:**
- `steps.validate.outputs.environment`
- `steps.validate.outputs.steps`
- `steps.determine_current.outputs.current_sha`

**Outputs:**
- `used_api` (string: 'true' | 'false')
- `api_target_sha` (string: 40-char hex)

**Regex Patterns:**
```javascript
/^[a-f0-9]{40}$/  // SHA validation in deployment list
```

**API Calls:**
- `github.rest.repos.listDeployments()` (paginated, limit 50)

**Key Logic:**
- Query deployment history for environment
- Filter to SHAs (40-char format only)
- Deduplicate by SHA (keep first successful deployment per SHA)
- Find current SHA index in history
- Calculate target: current_index + steps
- Bounds checking

**Failure Conditions:**
- Empty deployment history
- Current SHA not in history (uses newest as baseline)
- Target index out of bounds

#### Block 6: Lines 909-999 (91 lines)
**Step:** "Verify Coverage Gate"
**ID:** `verify_coverage`

**Condition:** `steps.validate.outputs.should_run == 'true'`

**Inputs Used:**
- `steps.determine_sha.outputs.final_sha`

**Outputs:**
- `error_message` (string)

**Hardcoded Values:**
```javascript
const requiredCheckName = 'test-coverage';
```

**Regex Patterns:**
```javascript
/Coverage\s+([\d.]+)%/
```

**API Calls:**
- `github.rest.checks.listForRef()`

**Key Logic:**
- Identical to deploy.yml coverage gate
- Query check runs for SHA
- Verify check exists and passed

**Failure Conditions:**
- Check not found
- Check conclusion !== 'success'

#### Block 7: Lines 1003-1060 (58 lines)
**Step:** "Post Coverage Gate Failure"

**Condition:** `failure() && steps.verify_coverage.outputs.error_message != ''`

**API Calls:**
- `github.rest.issues.createComment()`

#### Block 8: Lines 1064-1183 (120 lines)
**Step:** "Create GitHub Deployment"
**ID:** `create_deployment`

**Condition:** `steps.validate.outputs.should_run == 'true' && steps.verify_coverage.outputs.error_message == ''`

**Inputs Used:**
- `steps.validate.outputs.*`
- `steps.determine_sha.outputs.final_sha`

**Outputs:**
- `deployment_id` (string)

**API Calls:**
- `github.rest.repos.createDeployment()`
- `github.rest.repos.createDeploymentStatus()`

#### Block 9: Lines 1429-1512 (84 lines)
**Step:** "Post Ops Status Comment"

**Condition:** `always() && steps.validate.outputs.should_run == 'true'`

**API Calls:**
- `github.rest.issues.createComment()`

#### Block 10: Lines 1517-1572 (56 lines)
**Step:** "Update Deployment Status"

**Condition:** `always() && steps.create_deployment.outputs.deployment_id`

**API Calls:**
- `github.rest.repos.createDeploymentStatus()`

### Inline Bash Blocks

#### Block 1: Lines 530-555 (26 lines)
**Step:** "Determine Current SHA"
**ID:** `determine_current`

**Outputs:**
- `current_sha` (GITHUB_OUTPUT)
- `current_image` (GITHUB_OUTPUT)

**Key Actions:**
- Query running Docker container
- Extract SHA from image tag
- Validate SHA format

#### Block 2: Lines 734-898 (165 lines)
**Step:** "Determine Target SHA"
**ID:** `determine_sha`

**Inputs Used:**
- `steps.validate.outputs.action`
- `steps.validate.outputs.target_sha`
- `steps.resolve_sha.outputs.resolved_sha`
- `steps.determine_current.outputs.current_sha`
- `steps.compute_rollback_api.outputs.api_target_sha`

**Outputs:**
- `final_sha` (GITHUB_OUTPUT)

**Key Logic:**
- Three-way logic based on action:
  - **restart**: Use current SHA
  - **redeploy**: Use provided SHA > current SHA
  - **rollback**: Use provided SHA > API result > local history fallback
- Local history file parsing for rollback
- Complex index calculation for history-based rollback

**Failure Conditions:**
- restart: No current SHA available
- redeploy: No SHA provided and no current SHA
- rollback: All sources unavailable

#### Block 3: Lines 1197-1425 (229 lines)
**Step:** "Execute Ops Operation"
**ID:** `execute_ops`

**Inputs Used:**
- `steps.validate.outputs.action`
- `steps.validate.outputs.environment`
- `steps.determine_sha.outputs.final_sha`
- Environment variables

**Key Actions:**
- Docker container lifecycle (stop, run, exec)
- Health check loop
- History file recording
- Operation-specific logic dispatch

### Step Outputs

| Step ID | Output Name | Type | Used By |
|---------|-------------|------|---------|
| `validate` | `should_run` | string | All steps |
| `validate` | `action` | string | Multiple steps |
| `validate` | `environment` | string | Multiple steps |
| `validate` | `target_sha` | string | resolve_sha |
| `validate` | `steps` | string | compute_rollback |
| `validate` | `confirm` | string | - |
| `validate` | `container_name` | string | execute_ops |
| `validate` | `port` | string | execute_ops |
| `validate` | `requester` | string | Comments |
| `validate` | `skip_tagging` | string | - |
| `validate` | `error_message` | string | Error posting |
| `resolve_sha` | `resolved_sha` | string | determine_sha |
| `resolve_sha` | `is_tag` | string | - |
| `resolve_sha` | `original_ref` | string | - |
| `resolve_sha` | `ref_type` | string | - |
| `resolve_sha` | `error_message` | string | Error posting |
| `determine_current` | `current_sha` | string | determine_sha |
| `determine_current` | `current_image` | string | - |
| `compute_rollback_api` | `used_api` | string | - |
| `compute_rollback_api` | `api_target_sha` | string | determine_sha |
| `determine_sha` | `final_sha` | string | Coverage, Deploy |
| `verify_coverage` | `error_message` | string | Error posting |
| `create_deployment` | `deployment_id` | string | Update deployment |

---

## 🔐 SECURITY ARTIFACTS

### Authorization Allowlists

**Staging Authorized Users:**
- `ktamvada-cyber`
- `gromag`

**Production Authorized Users:**
- `ktamvada-cyber`
- `gromag`

**Locations:**
- `deploy.yml:87-95`
- `ops.yml:237-245`

### Ops Console Issue Number

**Value:** `2`
**Location:** `ops.yml:53` (env var `OPS_ISSUE_NUMBER`)

### Coverage Gate Check Name

**Value:** `'test-coverage'`
**Locations:**
- `deploy.yml:289`
- `ops.yml:913`

---

## 📊 REGEX PATTERNS

| Pattern | Purpose | Location |
|---------|---------|----------|
| `/^\[(staging\|prod)-(restart\|redeploy\|rollback)(?:\s+sha=([^\s\]]+))?(?:\s+steps=(\d+))?(?:\s+confirm=(yes))?\]$/` | Ops command parsing | ops.yml:175 |
| `/Coverage\s+([\d.]+)%/` | Extract coverage % from check title | deploy.yml:149, 353; ops.yml:984 |
| `/^[a-f0-9]{40}$/` | Validate full SHA format | ops.yml:361, 445, 612 |

---

## 🌐 GITHUB API USAGE

### Deployments API

**Endpoints Used:**
- `github.rest.repos.createDeployment()`
  - Locations: deploy.yml:247, ops.yml:1073
- `github.rest.repos.createDeploymentStatus()`
  - Locations: deploy.yml:268, 912; ops.yml:1096, 1531
- `github.rest.repos.listDeployments()`
  - Locations: ops.yml:585

**Payload Structure (deploy.yml):**
```javascript
{
  pr_number: prNumber,
  pr_branch: prBranch,
  pr_sha: prSha,
  triggered_by: context.payload.comment.user.login,
  comment_id: context.payload.comment.id
}
```

### Checks API

**Endpoints Used:**
- `github.rest.checks.create()`
  - Locations: test-coverage.yml:110
- `github.rest.checks.listForRef()`
  - Locations: deploy.yml:137, 292; ops.yml:917

### Pull Requests API

**Endpoints Used:**
- `github.rest.pulls.get()`
  - Locations: deploy.yml:112

### Issues/Comments API

**Endpoints Used:**
- `github.rest.issues.createComment()`
  - Locations: deploy.yml:378, 432, 522, 828; ops.yml:321, 485, 1009, 1435

### Git API

**Endpoints Used:**
- `github.rest.git.getRef()`
  - Locations: ops.yml:371, 395, 413
- `github.rest.git.getTag()`
  - Locations: ops.yml:383
- `github.rest.repos.getCommit()`
  - Locations: ops.yml:429

---

## 📈 SUMMARY STATISTICS

| Metric | Value |
|--------|-------|
| Total workflow files | 3 |
| Total workflow lines | 2,651 |
| Inline JavaScript blocks | 19 |
| Inline Bash blocks | 11 |
| Total step IDs | 15 |
| Total step outputs | 26 |
| Hardcoded authorization lists | 4 |
| Regex patterns | 3 |
| GitHub API endpoints used | 11 |
| Environment variables | 8 |

---

## ✅ SNAPSHOT COMPLETE

This snapshot represents the complete pre-refactor state of the `.github` directory.

**Critical Preservation Requirements:**
- All output names must remain identical
- All regex patterns must be preserved exactly
- All authorization lists must remain unchanged
- All API payload structures must be preserved
- All failure conditions must trigger identically
- All step ordering must be preserved

**Next Step:** Wait for approval to begin PHASE 1 extraction.

---

**Document Status:** LOCKED
**Modification:** PROHIBITED
**Version:** 1.0
