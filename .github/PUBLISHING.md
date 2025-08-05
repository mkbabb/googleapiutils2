# Publishing Setup

This project uses GitHub Actions with PyPI's trusted publishers for secure, automated publishing.

## Setup Instructions

### 1. Configure PyPI Trusted Publisher

Go to https://pypi.org/manage/project/googleapiutils2/settings/publishing/ and add a new GitHub publisher:

- **Owner**: mkbabb (or your GitHub username/org)
- **Repository name**: googleapiutils2
- **Workflow name**: publish.yml
- **Environment name**: release (recommended for security)

### 2. Configure TestPyPI Trusted Publisher (Optional)

For testing, configure the same on https://test.pypi.org/:

- **Owner**: mkbabb
- **Repository name**: googleapiutils2
- **Workflow name**: test-publish.yml
- **Environment name**: (leave empty for test)

### 3. Create GitHub Environment (Recommended)

In your GitHub repository settings:

1. Go to Settings → Environments
2. Create a new environment called "release"
3. Add protection rules:
   - Required reviewers (optional)
   - Restrict deployment branches to main/master

## Usage

### Automatic Publishing

1. Create a new release on GitHub
2. The workflow will automatically:
   - Build the package with UV
   - Publish to PyPI using trusted publishing

### Manual Publishing

Run the workflow manually from Actions tab → Publish to PyPI → Run workflow

### Test Publishing

Every push to master/main automatically publishes to TestPyPI for testing.

## Local Publishing (Emergency Only)

If GitHub Actions fails, you can publish locally:

```bash
# Build
uv build

# Publish with API token
uv publish --token <your-token>
```

## Benefits of Trusted Publishing

- No API tokens stored in GitHub secrets
- Automatic OIDC authentication
- More secure than password/token auth
- Audit trail in both GitHub and PyPI