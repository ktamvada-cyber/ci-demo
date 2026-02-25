# Operations Runbook

Day-to-day operational procedures for managing local deployment demo.

---

## Daily Operations

### Check Deployment Status

```bash
# List running containers
docker ps

# Expected output (both environments deployed):
# myapp-staging  ci-demo:abc123...  Up 2 hours  0.0.0.0:8001->8000/tcp
# myapp-prod     ci-demo:abc123...  Up 1 hour   0.0.0.0:8002->8000/tcp

# Check service health
curl http://localhost:8001/health
curl http://localhost:8002/health

# Check deployment metadata
curl http://localhost:8001/deployment-info
curl http://localhost:8002/deployment-info

# Check GitHub Deployments (shows PR branch/SHA, not main)
gh api repos/:owner/:repo/deployments \
  --jq '.[] | select(.environment == "staging") | {environment, ref: .ref[0:7], branch: .payload.pr_branch, status: .statuses_url}' \
  | head -1

gh api repos/:owner/:repo/deployments \
  --jq '.[] | select(.environment == "production") | {environment, ref: .ref[0:7], branch: .payload.pr_branch, status: .statuses_url}' \
  | head -1
```

### View Application Logs

```bash
# Staging logs (last 100 lines)
docker logs --tail 100 myapp-staging

# Production logs (last 100 lines)
docker logs --tail 100 myapp-prod

# Follow logs in real-time
docker logs -f myapp-staging

# Logs since specific time
docker logs --since 30m myapp-staging
```

### Inspect Container Configuration

```bash
# Full container details
docker inspect myapp-staging

# Specific fields
docker inspect --format='{{.Config.Image}}' myapp-staging
docker inspect --format='{{.State.Status}}' myapp-staging
docker inspect --format='{{.NetworkSettings.Ports}}' myapp-staging
docker inspect --format='{{range .Config.Env}}{{println .}}{{end}}' myapp-staging

# Example output:
# ENVIRONMENT=staging
# COMMIT_SHA=abc123...
# BUILD_TIMESTAMP=2024-02-24T10:30:00Z
# DEPLOYMENT_ID=987654321
# CONTAINER_NAME=myapp-staging
# PORT=8001
# IMAGE_DIGEST=sha256:def456...
# API_KEY=staging-key-value
# DB_HOST=staging-db.example.com
```

### List Docker Images

```bash
# All ci-demo images
docker images | grep ci-demo

# Expected output:
# ci-demo  abc123def456...  2 hours ago   150MB
# ci-demo  xyz789abc012...  1 day ago     148MB

# Check image size
docker images ci-demo --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Check image history
docker history ci-demo:abc123...
```

---

## Deployment Procedures

### Normal Staging Deployment

1. **Verify PR is ready:**
   ```bash
   gh pr view 42 --json state,mergeable,mergeStateStatus
   ```

2. **Comment on PR:**
   ```
   [staging]
   ```

3. **Monitor workflow:**
   ```bash
   gh run list --limit 1
   gh run view --log
   ```

4. **Verify deployment:**
   ```bash
   curl http://localhost:8001/
   docker ps | grep myapp-staging
   docker logs --tail 20 myapp-staging
   ```

### Normal Production Deployment

1. **Ensure staging is deployed and tested:**
   ```bash
   curl http://localhost:8001/deployment-info | jq '.commit_sha'
   # Verify this is the SHA you want in production
   ```

2. **Comment on PR:**
   ```
   [prod]
   ```

3. **Approve in GitHub UI:**
   - Navigate to Actions → workflow run
   - Click "Review deployments"
   - Verify commit SHA
   - Click "Approve and deploy"

4. **Monitor workflow:**
   ```bash
   gh run view --log
   ```

5. **Verify deployment:**
   ```bash
   curl http://localhost:8002/
   docker ps | grep myapp-prod
   docker logs --tail 20 myapp-prod
   ```

### Emergency Rollback (Manual)

**Scenario:** Production deployment broke, need to rollback immediately.

```bash
# Step 1: Find previous working version
docker images | grep ci-demo

# Step 2: Stop broken production container
docker stop myapp-prod
docker rm myapp-prod

# Step 3: Start previous version
ROLLBACK_SHA="abc123def456..."  # Replace with previous working SHA

docker run -d \
  --name myapp-prod \
  -p 8002:8000 \
  -e ENVIRONMENT=production \
  -e DEPLOYMENT_ID=manual-rollback-$(date +%s) \
  -e CONTAINER_NAME=myapp-prod \
  -e PORT=8002 \
  -e IMAGE_DIGEST=$(docker inspect --format='{{.Id}}' ci-demo:${ROLLBACK_SHA}) \
  -e API_KEY="your-production-api-key" \
  -e DB_HOST="your-production-db-host" \
  ci-demo:${ROLLBACK_SHA}

# Step 4: Verify rollback
curl http://localhost:8002/deployment-info | jq '.commit_sha'
# Should show ROLLBACK_SHA

# Step 5: Post notification to PR (manual)
# Comment on PR explaining manual rollback
```

---

## Troubleshooting

### Container Won't Start

**Symptom:** Deployment fails with "Container failed to start"

**Diagnosis:**
```bash
# Check if container exists
docker ps -a | grep myapp-staging

# View container logs (even if stopped)
docker logs myapp-staging

# Inspect exit code
docker inspect --format='{{.State.ExitCode}}' myapp-staging
```

**Common causes:**

**Exit code 125:** Docker daemon error (port conflict, name conflict)
```bash
# Check for port conflicts
lsof -i :8001

# Check for name conflicts
docker ps -a | grep myapp-staging
docker rm myapp-staging
```

**Exit code 1:** Application crash during startup
```bash
# Check application logs
docker logs myapp-staging

# Common issues:
# - Missing environment variable
# - Port already in use inside container
# - Dependency import error
# - Database connection failure
```

**Exit code 137:** Out of memory (OOM killed)
```bash
# Check Docker memory limits
docker stats --no-stream myapp-staging

# Increase container memory limit (modify workflow)
docker run -d --memory=512m ...
```

### Health Check Fails

**Symptom:** Deployment succeeds but service status is "running_unverified"

**Diagnosis:**
```bash
# Test from inside container
docker exec myapp-staging curl localhost:8000/
# If this works but http://localhost:8001/ doesn't, port mapping issue

# Test from host
curl http://localhost:8001/
curl -v http://localhost:8001/  # Verbose output

# Check port mapping
docker port myapp-staging
# Should show: 8000/tcp -> 0.0.0.0:8001

# Check application is listening on 0.0.0.0, not 127.0.0.1
docker exec myapp-staging netstat -tuln | grep 8000
# Should show: 0.0.0.0:8000 LISTEN
```

**Common causes:**

1. **Application startup delay:** Increase MAX_RETRIES or retry interval in workflow
2. **Application listening on 127.0.0.1:** Change app to bind to `0.0.0.0`
3. **Port conflict:** Another container using same host port
4. **Firewall:** Host firewall blocking port (unlikely on localhost)

### Image Build Fails

**Symptom:** Deployment fails during `docker build`

**Diagnosis:**
```bash
# View workflow logs
gh run view --log

# Search for error
gh run view --log | grep -A 10 "ERROR"

# Reproduce locally
git checkout <SHA>
docker build --build-arg COMMIT_SHA=<SHA> --build-arg BUILD_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ") -t ci-demo:<SHA> .
```

**Common causes:**

**Network timeout:**
```bash
# Retry build
Comment [staging] again on PR
```

**Disk space:**
```bash
docker system df
docker system prune -a  # Remove unused images
df -h  # Check disk space
```

**Build arg issues:**
```Dockerfile
# Dockerfile must declare ARG before using
ARG COMMIT_SHA
ENV COMMIT_SHA=$COMMIT_SHA  # Use build arg
```

**Dependency failure:**
```bash
# Test dependencies locally
npm install  # or pip install -r requirements.txt

# Check for dependency version conflicts
npm ls  # or pip list
```

### Workflow Stuck on "Queued"

**Symptom:** Workflow run shows "Queued" for >5 minutes

**Cause:** Self-hosted runner is offline

**Diagnosis:**
```bash
# On runner machine
ps aux | grep run.sh

# Check runner logs
cd /path/to/runner
cat _diag/Runner_*.log
```

**Solution:**
```bash
# Restart runner
cd /path/to/runner
./run.sh
```

### Workflow Times Out

**Symptom:** Workflow fails after 15 minutes with "The operation was canceled"

**Causes:**
1. **Approval wait time:** Production approval took >15 minutes
2. **Slow build:** Docker build took >15 minutes
3. **Slow health check:** Service took >15 minutes to respond

**Solution:**

**For approval timeout:**
```yaml
# Increase timeout (edit workflow)
timeout-minutes: 30  # Allow more time for approval
```

**For slow build:**
```bash
# Optimize Dockerfile
# - Use smaller base image
# - Leverage build cache
# - Combine RUN commands
```

**For slow health check:**
```bash
# Check application startup logs
docker logs myapp-staging

# Optimize application startup
# - Lazy-load heavy dependencies
# - Reduce database connections during startup
# - Use health check endpoint that responds quickly
```

---

## Maintenance

### Clean Up Old Images

**Recommendation:** Run weekly to avoid disk space issues.

```bash
# List all images sorted by size
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | sort -k 3 -h -r

# Remove images older than 7 days
docker images ci-demo --format "{{.ID}} {{.CreatedAt}}" | \
  awk '$2 < "'$(date -d '7 days ago' +%Y-%m-%d)'" {print $1}' | \
  xargs -r docker rmi

# Or remove all unused images
docker image prune -a --filter "until=168h"  # 7 days

# Remove dangling images (untagged)
docker image prune
```

### Rotate Containers

**Recommendation:** Restart containers weekly to apply OS updates.

```bash
# Staging
docker restart myapp-staging
docker logs --tail 20 myapp-staging  # Verify restart

# Production (do during maintenance window)
docker restart myapp-prod
docker logs --tail 20 myapp-prod
```

### Check Runner Disk Space

```bash
# Disk usage summary
df -h

# Docker disk usage
docker system df

# Check for large log files
du -sh /var/lib/docker/containers/*/*-json.log | sort -h -r | head -5

# Truncate large logs
sudo sh -c 'echo "" > /var/lib/docker/containers/<container-id>/<container-id>-json.log'
```

### Update GitHub Runner

```bash
# Stop runner
cd /path/to/runner
sudo ./svc.sh stop

# Download latest runner
# (Follow GitHub's update instructions)

# Start runner
sudo ./svc.sh start

# Verify
./run.sh --version
```

---

## Emergency Procedures

### All Deployments Failing

**Checklist:**

1. **Check runner is online:**
   ```bash
   ps aux | grep run.sh
   ./run.sh  # Restart if needed
   ```

2. **Check Docker daemon is running:**
   ```bash
   docker ps
   sudo systemctl status docker
   sudo systemctl start docker
   ```

3. **Check disk space:**
   ```bash
   df -h
   docker system prune -a  # If disk full
   ```

4. **Check network connectivity:**
   ```bash
   ping github.com
   curl -I https://api.github.com
   ```

5. **Review recent workflow changes:**
   ```bash
   git log --oneline -10 -- .github/workflows/deploy.yml
   git diff HEAD~1 .github/workflows/deploy.yml
   ```

### Production Container Crashed

**Immediate response:**

1. **Check if container is running:**
   ```bash
   docker ps | grep myapp-prod
   docker ps -a | grep myapp-prod
   ```

2. **View crash logs:**
   ```bash
   docker logs --tail 100 myapp-prod
   ```

3. **Attempt restart:**
   ```bash
   docker start myapp-prod
   docker logs -f myapp-prod
   ```

4. **If restart fails, rollback:**
   ```bash
   # See "Emergency Rollback" section above
   ```

5. **Notify team:**
   - Post incident in Slack/chat
   - Create GitHub issue with logs
   - Schedule post-mortem

### Runner Machine Reboot

**Impact:** All running containers stop.

**Recovery:**

1. **After reboot, check Docker is running:**
   ```bash
   sudo systemctl status docker
   sudo systemctl start docker
   ```

2. **Restart runner:**
   ```bash
   cd /path/to/runner
   ./run.sh
   ```

3. **Containers do NOT auto-restart** (no restart policy set in workflow)

4. **Manually redeploy:**
   - Find last deployed SHAs in PR comments
   - Comment `[staging]` and `[prod]` on respective PRs
   - Or manually start containers (see "Emergency Rollback")

---

## Monitoring Commands

### One-Liner Health Check

```bash
# Check both environments
for env in staging prod; do
  port=$([[ $env == "staging" ]] && echo 8001 || echo 8002)
  echo "=== $env (localhost:$port) ==="
  curl -s http://localhost:$port/deployment-info | jq '{env: .environment, commit: .commit_sha, status: .status}'
  docker inspect --format='{{.State.Status}} ({{.State.Health.Status}})' myapp-$env 2>/dev/null || echo "Container not found"
  echo
done
```

### Continuous Monitoring

```bash
# Watch container status (refreshes every 2 seconds)
watch -n 2 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'

# Monitor logs from both environments
docker logs -f myapp-staging 2>&1 | sed 's/^/[STAGING] /' &
docker logs -f myapp-prod 2>&1 | sed 's/^/[PROD] /' &
wait
```

### Deployment History

```bash
# From GitHub Deployments UI (recommended)
# Navigate to: Repository → Environments → staging or production
# Shows: Branch, commit SHA, status, timestamps for all deployments

# From GitHub API (programmatic access)
gh api repos/:owner/:repo/deployments --jq '.[] | select(.environment == "staging") | {sha: .sha, created: .created_at, url: .payload.pr_branch}'

gh api repos/:owner/:repo/deployments --jq '.[] | select(.environment == "production") | {sha: .sha, created: .created_at, url: .payload.pr_branch}'

# From workflow runs
gh run list --workflow="Deploy on Comment" --limit 20

# From PR comments (find deployment status comments)
gh pr list --state all --limit 10 --json number,title | jq -r '.[] | "\(.number) \(.title)"'

# From Docker images (shows all deployed versions)
docker images ci-demo --format "table {{.Tag}}\t{{.CreatedAt}}\t{{.Size}}"
```

---

## Runbook Checklist Templates

### Pre-Deployment Checklist

- [ ] PR is open and mergeable_state is "clean"
- [ ] All required status checks passed
- [ ] Code has been reviewed and approved
- [ ] For production: Staging has been deployed and tested
- [ ] Self-hosted runner is online (`gh run list` doesn't show "Queued" indefinitely)
- [ ] Disk space available (`df -h` shows >20% free on runner)
- [ ] Ports 8001/8002 are not in use (`lsof -i :8001 -i :8002`)

### Post-Deployment Checklist

- [ ] Workflow run shows success (green checkmark)
- [ ] Deployment status comment posted to PR
- [ ] Container is running (`docker ps | grep myapp-{environment}`)
- [ ] Service responds to HTTP requests (`curl http://localhost:{port}/`)
- [ ] Returned commit SHA matches deployed SHA
- [ ] Application logs show no errors (`docker logs --tail 50 myapp-{environment}`)
- [ ] For production: Monitor for 10 minutes for crashes

### Rollback Checklist

- [ ] Identify rollback target SHA (from previous deployment comment)
- [ ] Verify rollback image exists (`docker images | grep ci-demo:<SHA>`)
- [ ] Stop current container (`docker stop myapp-{environment}`)
- [ ] Remove current container (`docker rm myapp-{environment}`)
- [ ] Start rollback container (see "Emergency Rollback" commands)
- [ ] Verify rollback succeeded (`curl http://localhost:{port}/deployment-info`)
- [ ] Post notification to PR explaining rollback
- [ ] Create incident report with logs and root cause
