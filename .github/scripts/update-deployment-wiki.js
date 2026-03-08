/**
 * GitHub Wiki Deployment History Updater
 *
 * This script generates and updates the Deployment-History.md page in the GitHub Wiki
 * with the latest deployment information from both staging and production environments.
 */

module.exports = async ({ github, context, core }) => {
  const owner = context.repo.owner;
  const repo = context.repo.repo;

  core.info('🚀 Starting deployment history wiki update...');
  core.info(`Repository: ${owner}/${repo}`);

  // Cache for commit details to avoid duplicate API calls
  const commitCache = new Map();
  const prCache = new Map();

  /**
   * Fetch deployments for a specific environment
   */
  async function fetchDeployments(environment, limit = 10) {
    core.info(`\n📊 Fetching ${environment} deployments...`);

    try {
      const deploymentsResponse = await github.rest.repos.listDeployments({
        owner,
        repo,
        environment,
        per_page: 50 // Fetch enough to get 10 successful deployments
      });

      const deployments = deploymentsResponse.data;

      // Sort by created_at descending (newest first) for consistent ordering
      deployments.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

      core.info(`Found ${deployments.length} total deployments for ${environment}`);

      // Fetch deployment statuses and filter for successful ones
      const successfulDeployments = [];

      for (const deployment of deployments) {
        if (successfulDeployments.length >= limit) {
          break;
        }

        // Skip deployments without description (not created by our workflows)
        if (!deployment.description) {
          continue;
        }

        try {
          const statusesResponse = await github.rest.repos.listDeploymentStatuses({
            owner,
            repo,
            deployment_id: deployment.id
          });

          const statuses = statusesResponse.data;

          // Sort by created_at descending to get latest status first (guaranteed order)
          const latestStatus = statuses.sort(
            (a, b) => new Date(b.created_at) - new Date(a.created_at)
          )[0];

          // Check if deployment ever reached 'success' state (before possibly becoming 'inactive')
          const hasSuccessState = statuses.some(s => s.state === 'success');

          if (latestStatus && hasSuccessState) {
            successfulDeployments.push({
              deployment,
              status: latestStatus
            });
          }
        } catch (error) {
          core.warning(`Failed to fetch status for deployment ${deployment.id}: ${error.message}`);
        }
      }

      core.info(`Found ${successfulDeployments.length} successful deployments for ${environment}`);
      return successfulDeployments;

    } catch (error) {
      core.error(`Failed to fetch deployments for ${environment}: ${error.message}`);
      return [];
    }
  }

  /**
   * Fetch commit details
   */
  async function fetchCommitDetails(sha) {
    // Check cache first
    if (commitCache.has(sha)) {
      return commitCache.get(sha);
    }

    try {
      const commitResponse = await github.rest.repos.getCommit({
        owner,
        repo,
        ref: sha
      });

      const commitData = {
        author: commitResponse.data.commit.author.name,
        date: commitResponse.data.commit.author.date,
        message: commitResponse.data.commit.message.split('\n')[0] // First line only
      };

      // Cache the result
      commitCache.set(sha, commitData);
      return commitData;
    } catch (error) {
      core.warning(`Failed to fetch commit details for ${sha}: ${error.message}`);
      const fallbackData = {
        author: 'Unknown',
        date: new Date().toISOString(),
        message: 'N/A'
      };
      commitCache.set(sha, fallbackData);
      return fallbackData;
    }
  }

  /**
   * Fetch PR associated with commit
   */
  async function fetchPRForCommit(sha) {
    // Check cache first
    if (prCache.has(sha)) {
      return prCache.get(sha);
    }

    try {
      const prsResponse = await github.rest.repos.listPullRequestsAssociatedWithCommit({
        owner,
        repo,
        commit_sha: sha
      });

      const prs = prsResponse.data;
      if (prs && prs.length > 0) {
        // When multiple PRs share the same SHA, prefer:
        // 1. Open PRs over closed/merged
        // 2. Most recently updated PR
        const sortedPrs = prs.sort((a, b) => {
          // Prefer open PRs
          if (a.state === 'open' && b.state !== 'open') return -1;
          if (a.state !== 'open' && b.state === 'open') return 1;
          // Then prefer most recently updated
          return new Date(b.updated_at) - new Date(a.updated_at);
        });

        const selectedPr = sortedPrs[0];
        const prData = {
          number: selectedPr.number,
          title: selectedPr.title
        };
        // Cache the result
        prCache.set(sha, prData);
        return prData;
      }
    } catch (error) {
      core.warning(`Failed to fetch PR for commit ${sha}: ${error.message}`);
    }

    // Cache null result to avoid repeated lookups
    prCache.set(sha, null);
    return null;
  }

  /**
   * Extract operation type from deployment description or payload
   */
  function extractOperationType(deployment) {
    const description = deployment.description || '';
    const payload = deployment.payload || {};

    // Check description for operation keywords
    if (description.includes('rollback')) return 'rollback';
    if (description.includes('redeploy')) return 'redeploy';
    if (description.includes('restart')) return 'restart';

    // Check payload
    if (payload.action) {
      return payload.action;
    }

    // Default to deploy for PR-based deployments
    return 'deploy';
  }

  /**
   * Extract trigger information
   */
  function extractTrigger(deployment) {
    const payload = deployment.payload || {};

    // Check for PR trigger - prioritize payload.pr_number
    if (payload.pr_number) {
      return {
        type: 'PR',
        number: payload.pr_number
      };
    }

    // Fallback to other PR detection methods
    if (payload.pull_request || deployment.ref?.startsWith('refs/pull/')) {
      const prMatch = deployment.ref?.match(/refs\/pull\/(\d+)/);
      return {
        type: 'PR',
        number: prMatch ? prMatch[1] : (payload.pull_request?.number || 'N/A')
      };
    }

    // Check for issue trigger (ops console)
    if (payload.issue_number) {
      return {
        type: 'Issue',
        number: payload.issue_number
      };
    }

    // Check for workflow_dispatch
    if (payload.workflow_dispatch) {
      return {
        type: 'Manual',
        number: null
      };
    }

    // Default
    return {
      type: 'Manual',
      number: null
    };
  }

  /**
   * Format a deployment row for the table
   */
  async function formatDeploymentRow(item, includeWorkflow = true) {
    const { deployment, status } = item;
    const sha = deployment.ref;
    const shortSha = sha.substring(0, 7);
    const commitLink = `[${shortSha}](https://github.com/${owner}/${repo}/commit/${sha})`;

    // Fetch commit details
    const commit = await fetchCommitDetails(sha);

    // Get PR number from deployment payload (triggering PR) instead of commit association
    // This shows which PR triggered the deployment, not where the code originated
    const payload = deployment.payload || {};
    let prNumber = payload.pr_number;

    // Fallback to commit association for older deployments without payload
    if (!prNumber) {
      const prFromCommit = await fetchPRForCommit(sha);
      prNumber = prFromCommit ? prFromCommit.number : null;
    }

    const prLink = prNumber ? `[#${prNumber}](https://github.com/${owner}/${repo}/pull/${prNumber})` : 'N/A';

    // Extract operation and trigger
    const operation = extractOperationType(deployment);
    const trigger = extractTrigger(deployment);
    const triggerText = trigger.number ? `${trigger.type} #${trigger.number}` : trigger.type;

    // Deployment metadata
    const deployedBy = deployment.creator?.login || 'unknown';
    const deploymentTime = new Date(status.created_at).toLocaleString('en-US', {
      timeZone: 'UTC',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short'
    });

    const commitTime = new Date(commit.date).toLocaleString('en-US', {
      timeZone: 'UTC',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short'
    });

    // Workflow run link
    const workflowRunId = deployment.payload?.workflow_run_id || status.log_url?.split('/runs/')[1] || 'N/A';
    const workflowLink = workflowRunId !== 'N/A'
      ? `[${workflowRunId}](https://github.com/${owner}/${repo}/actions/runs/${workflowRunId})`
      : 'N/A';

    if (includeWorkflow) {
      return `| ${deployment.id} | ${commitLink} | ${prLink} | ${commit.message} | ${commit.author} | ${commitTime} | ${deployedBy} | ${operation} | ${triggerText} | ${workflowLink} |`;
    } else {
      return `| ${commitLink} | ${prLink} | ${commit.author} | ${deployedBy} | ${deploymentTime} |`;
    }
  }

  /**
   * Generate unique deployment timeline
   */
  function generateTimeline(deploymentItems) {
    const uniqueCommits = new Map();

    for (const item of deploymentItems) {
      const sha = item.deployment.ref;
      if (!uniqueCommits.has(sha)) {
        uniqueCommits.set(sha, item);
      }
    }

    return Array.from(uniqueCommits.values());
  }

  /**
   * Generate markdown content for the wiki
   */
  async function generateMarkdown() {
    core.info('\n📝 Generating markdown content...');

    // Fetch deployments for both environments
    const stagingDeployments = await fetchDeployments('staging', 10);
    const productionDeployments = await fetchDeployments('production', 10);

    const timestamp = new Date().toLocaleString('en-US', {
      timeZone: 'UTC',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    });

    let markdown = `# CI/CD Deployment History\n\n`;
    markdown += `**Last Updated:** ${timestamp}\n\n`;
    markdown += `This page is automatically generated and updated after every successful deployment.\n\n`;
    markdown += `---\n\n`;

    // STAGING SECTION
    markdown += `# 🔷 STAGING\n\n`;

    if (stagingDeployments.length > 0) {
      markdown += `## Current Deployment\n\n`;
      markdown += `| Commit | PR | Author | Deployed By | Deployment Time |\n`;
      markdown += `|--------|----|---------|--------------|-----------------|\n`;
      markdown += await formatDeploymentRow(stagingDeployments[0], false) + '\n\n';

      markdown += `---\n\n`;
      markdown += `## Recent Deployments (Latest 10)\n\n`;
      markdown += `| Deployment ID | Commit | PR | Commit Message | Commit Author | Commit Time | Deployed By | Operation | Trigger | Workflow |\n`;
      markdown += `|---------------|--------|-----|----------------|---------------|-------------|-------------|-----------|---------|----------|\n`;

      for (const item of stagingDeployments) {
        markdown += await formatDeploymentRow(item, true) + '\n';
      }

      markdown += `\n---\n\n`;
      markdown += `## Unique Deployment Timeline\n\n`;
      const stagingTimeline = generateTimeline(stagingDeployments);
      markdown += `Total unique commits deployed: **${stagingTimeline.length}**\n\n`;

      for (const item of stagingTimeline) {
        const sha = item.deployment.ref;
        const shortSha = sha.substring(0, 7);
        const commit = await fetchCommitDetails(sha);
        const pr = await fetchPRForCommit(sha);
        const prText = pr ? ` (PR #${pr.number})` : '';
        markdown += `- [\`${shortSha}\`](https://github.com/${owner}/${repo}/commit/${sha}) - ${commit.message}${prText}\n`;
      }
    } else {
      markdown += `No successful deployments found for staging.\n`;
    }

    markdown += `\n---\n\n`;

    // PRODUCTION SECTION
    markdown += `# 🔶 PRODUCTION\n\n`;

    if (productionDeployments.length > 0) {
      markdown += `## Current Deployment\n\n`;
      markdown += `| Commit | PR | Author | Deployed By | Deployment Time |\n`;
      markdown += `|--------|----|---------|--------------|-----------------|\n`;
      markdown += await formatDeploymentRow(productionDeployments[0], false) + '\n\n';

      markdown += `---\n\n`;
      markdown += `## Recent Deployments (Latest 10)\n\n`;
      markdown += `| Deployment ID | Commit | PR | Commit Message | Commit Author | Commit Time | Deployed By | Operation | Trigger | Workflow |\n`;
      markdown += `|---------------|--------|-----|----------------|---------------|-------------|-------------|-----------|---------|----------|\n`;

      for (const item of productionDeployments) {
        markdown += await formatDeploymentRow(item, true) + '\n';
      }

      markdown += `\n---\n\n`;
      markdown += `## Unique Deployment Timeline\n\n`;
      const productionTimeline = generateTimeline(productionDeployments);
      markdown += `Total unique commits deployed: **${productionTimeline.length}**\n\n`;

      for (const item of productionTimeline) {
        const sha = item.deployment.ref;
        const shortSha = sha.substring(0, 7);
        const commit = await fetchCommitDetails(sha);
        const pr = await fetchPRForCommit(sha);
        const prText = pr ? ` (PR #${pr.number})` : '';
        markdown += `- [\`${shortSha}\`](https://github.com/${owner}/${repo}/commit/${sha}) - ${commit.message}${prText}\n`;
      }
    } else {
      markdown += `No successful deployments found for production.\n`;
    }

    markdown += `\n---\n\n`;
    markdown += `*This page is automatically maintained by the CI/CD deployment workflows.*\n`;

    core.info('✅ Markdown content generated successfully');
    return markdown;
  }

  // Generate and return the markdown
  const content = await generateMarkdown();
  return content;
};
