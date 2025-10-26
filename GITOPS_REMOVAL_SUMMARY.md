# GitOps Feature Removal Summary

## Overview
All GitOps features have been completely removed from the FleetImporter AutoPkg processor due to limitations in Fleet's current GitOps implementation. The processor now focuses exclusively on uploading software packages directly to Fleet via the REST API.

## Changes Made

### Code Reduction
- **Old version**: 718 lines
- **New version**: 549 lines
- **Lines removed**: 169 lines (23.5% reduction)

### Removed Features
1. **Git repository operations**
   - Git cloning and branching
   - Commit creation and pushing
   - Branch management

2. **GitHub integration**
   - Pull request creation
   - PR label management
   - Reviewer assignment
   - PR body generation

3. **YAML file management**
   - Software YAML file creation/updating
   - Team YAML references
   - Package YAML formatting

4. **GitOps workflow helpers**
   - `_slugify()` - Slug generation for Git paths
   - `_git()` - Git command execution
   - `_git_safe_commit()` - Safe commit creation
   - `_scan_software_packages()` - Package scanning
   - `_read_yaml()` - YAML reading
   - `_write_yaml()` - YAML writing
   - `_write_or_update_package_yaml()` - Package YAML management
   - `_pr_body()` - PR body generation
   - `_pr_body_shared()` - Shared PR body generation
   - `_open_pull_request()` - PR creation
   - `_find_existing_pr_url()` - PR lookup
   - `_derive_github_repo()` - GitHub repo parsing

### Removed Dependencies
- `PyYAML` - No longer required
- `subprocess` - No longer needed for Git operations
- `tempfile` - No longer needed for temporary Git repos
- `re` - No longer needed for slug generation
- Git CLI - No longer required

### Removed Input Variables
- `use_gitops` - Mode control
- `git_repo_url` - Git repository URL
- `git_base_branch` - Base branch name
- `git_author_name` - Git commit author
- `git_author_email` - Git commit email
- `software_dir` - Software YAML directory
- `package_yaml_suffix` - YAML file suffix
- `team_yaml_package_path_prefix` - Team YAML path prefix
- `team_yaml_path` - Team YAML file path (deprecated)
- `github_repo` - GitHub repository
- `github_token` - GitHub API token
- `pr_labels` - PR labels
- `PR_REVIEWER` - PR reviewer
- `software_slug` - File slug for YAML
- `branch_prefix` - Branch name prefix

### Removed Output Variables
- `git_branch` - Created branch name
- `pull_request_url` - PR URL

### Retained Functionality
The processor now focuses on core Fleet API operations:

1. **Package Upload**
   - Direct upload to Fleet via REST API
   - Package verification and deduplication
   - Version conflict detection

2. **Fleet Configuration**
   - Self-service availability
   - Automatic installation policies
   - Label-based targeting (include/exclude)
   - Custom install/uninstall/pre-install/post-install scripts

3. **Fleet Integration**
   - Version detection and compatibility checking
   - Existing package detection
   - SHA-256 hash calculation and verification

## Migration Guide

### For Existing Recipes
Recipes using this processor need to remove all GitOps-related arguments:

**Before (GitOps mode):**
```yaml
- Arguments:
    pkg_path: '%pkg_path%'
    software_title: '%NAME%'
    version: '%version%'
    fleet_api_base: 'https://fleet.example.com'
    fleet_api_token: '%FLEET_API_TOKEN%'
    team_id: '1'
    git_repo_url: 'https://github.com/example/fleet-gitops.git'
    github_token: '%FLEET_GITOPS_GITHUB_TOKEN%'
    self_service: true
  Processor: FleetImporter
```

**After (Direct mode only):**
```yaml
- Arguments:
    pkg_path: '%pkg_path%'
    software_title: '%NAME%'
    version: '%version%'
    fleet_api_base: 'https://fleet.example.com'
    fleet_api_token: '%FLEET_API_TOKEN%'
    team_id: '1'
    self_service: true
    labels_include_any:
      - workstations
    automatic_install: false
  Processor: FleetImporter
```

### Environment Variables
No longer needed:
- `FLEET_GITOPS_GITHUB_TOKEN`
- `PR_REVIEWER`
- `GIT_TERMINAL_PROMPT`

Still required:
- `FLEET_API_TOKEN` (or pass via `fleet_api_token` argument)

## Testing
All AutoPkg code style requirements pass:
- ✅ Python syntax validation (`python3 -m py_compile`)
- ✅ Black formatting (`python3 -m black --check`)
- ✅ Import sorting (`python3 -m isort --check-only`)
- ✅ Flake8 linting (`python3 -m flake8`)

## Benefits
1. **Simplicity**: Reduced code complexity and maintenance burden
2. **Fewer Dependencies**: No longer requires PyYAML, Git CLI, or GitHub tokens
3. **Faster Execution**: No Git operations or PR creation overhead
4. **Clearer Purpose**: Focused solely on Fleet API integration
5. **Easier Debugging**: Simpler code path with fewer moving parts

## Date
October 26, 2025
