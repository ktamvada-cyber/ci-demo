# Phase 1 Setup Instructions

## ⚠️ REQUIRED: Create Repository Variables

Before deploying Phase 1 workflow changes, create these repository variables:

### Via GitHub CLI:

```bash
# Set repository variables
gh variable set VM_HOST --body "192.168.64.2"
gh variable set VM_USER --body "deploy"
gh variable set VM_APP_PATH --body "/var/www/voicemodal"
gh variable set VM_SERVICE_NAME --body "convirza-voiceagent"

# Verify variables were created
gh variable list
```

### Via GitHub Web UI:

1. Navigate to: Settings → Secrets and variables → Actions → Variables tab
2. Click "New repository variable"
3. Create each variable:
   - Name: `VM_HOST`, Value: `192.168.64.2`
   - Name: `VM_USER`, Value: `deploy`
   - Name: `VM_APP_PATH`, Value: `/var/www/voicemodal`
   - Name: `VM_SERVICE_NAME`, Value: `convirza-voiceagent`

### Via GitHub API:

```bash
ORG_OR_USER="your-username"
REPO="your-repo"
TOKEN="your-github-token"

curl -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$ORG_OR_USER/$REPO/actions/variables \
  -d '{"name":"VM_HOST","value":"192.168.64.2"}'

curl -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$ORG_OR_USER/$REPO/actions/variables \
  -d '{"name":"VM_USER","value":"deploy"}'

curl -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$ORG_OR_USER/$REPO/actions/variables \
  -d '{"name":"VM_APP_PATH","value":"/var/www/voicemodal"}'

curl -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$ORG_OR_USER/$REPO/actions/variables \
  -d '{"name":"VM_SERVICE_NAME","value":"convirza-voiceagent"}'
```

## Verification

After creating variables, verify they exist:

```bash
gh variable list
```

Expected output:
```
VM_APP_PATH      /var/www/voicemodal     Updated YYYY-MM-DD
VM_HOST          192.168.64.2             Updated YYYY-MM-DD
VM_SERVICE_NAME  convirza-voiceagent     Updated YYYY-MM-DD
VM_USER          deploy                   Updated YYYY-MM-DD
```

## Behavior Guarantee

Once variables are created with these exact values, workflow behavior is **IDENTICAL** to the current implementation.

- ✅ All commands parse identically
- ✅ All SSH connections use same credentials
- ✅ All deployment paths unchanged
- ✅ All service names unchanged
