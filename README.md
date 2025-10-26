# FleetImporter AutoPkg Processor

Upload freshly built installers to Fleet using the Software API. This processor is designed for CI use in GitHub Actions and can also be run locally.

> **⚠️ Experimental:** This processor uses Fleet's [experimental software management API](https://fleetdm.com/docs/rest-api/rest-api#list-software), which is subject to breaking changes. Fleet may introduce API changes that require corresponding updates to this processor. **Production use is not recommended** due to the experimental nature of the underlying Fleet API.

---

## Features

- Uploads `.pkg` files to Fleet for specific teams
- Configures software deployment settings via Fleet API:
  - Self-service availability
  - Automatic installation policies
  - Host targeting via labels (include/exclude)
  - Custom install/uninstall/pre-install/post-install scripts
- Detects and skips duplicate package uploads
- Idempotent where practical and fails loudly on API errors
- Compatible with AutoPkg's YAML recipe format

---

## Requirements

- **macOS**: Required for AutoPkg execution
- **Python 3.9+**: For the FleetImporter processor
- **AutoPkg 2.7+**: For recipe processing
- **Fleet API Access**: Fleet server v4.74.0+ with software management permissions

---

## Why YAML?

AutoPkg [supports both XML (plist) and YAML recipe formats](https://github.com/autopkg/autopkg/wiki/Recipe-Format#overview). I personally find YAML more readable and maintainable than XML, especially for recipes that may be edited by hand or reviewed in code. YAML's indentation and lack of angle brackets make it easier to scan and less error-prone for most users.

---

## Installation

### 1. Install AutoPkg

```bash
# Using Homebrew (recommended)
brew install autopkg

# Verify installation
autopkg version
```

### 2. Add Recipe Repositories

```bash
# Add common AutoPkg recipe repos
autopkg repo-add https://github.com/autopkg/recipes.git
autopkg repo-add https://github.com/autopkg/homebysix-recipes.git

# Add this repo for FleetImporter processor
autopkg repo-add https://github.com/kitzy/fleetimporter.git
```

### 3. Configure Environment Variables

You can configure Fleet API credentials in two ways:

**Option A: Environment Variables (for CI/CD)**

```bash
export FLEET_API_BASE="https://fleet.example.com"
export FLEET_API_TOKEN="your-fleet-api-token"
export FLEET_TEAM_ID="1"
```

**Option B: AutoPkg Preferences (for local use)**

Set preferences in AutoPkg's plist file:

```bash
# Set Fleet API credentials
defaults write com.github.autopkg FLEET_API_BASE "https://fleet.example.com"
defaults write com.github.autopkg FLEET_API_TOKEN "your-fleet-api-token"
defaults write com.github.autopkg FLEET_TEAM_ID "1"

# Verify settings
defaults read com.github.autopkg FLEET_API_BASE
defaults read com.github.autopkg FLEET_API_TOKEN
defaults read com.github.autopkg FLEET_TEAM_ID
```

This stores the values in `~/Library/Preferences/com.github.autopkg.plist` so you don't need to export environment variables for each terminal session.

---

## Usage

### Basic Recipe Example

Here's a minimal recipe that downloads and uploads Google Chrome to Fleet:

```yaml
Description: 'Builds GoogleChrome.pkg and uploads to Fleet'
Identifier: com.github.kitzy.fleet.GoogleChrome
Input:
  NAME: Google Chrome
MinimumVersion: '2.0'
ParentRecipe: com.github.autopkg.pkg.googlechrome
Process:
- Arguments:
    pkg_path: '%pkg_path%'
    software_title: '%NAME%'
    version: '%version%'
    fleet_api_base: '%FLEET_API_BASE%'
    fleet_api_token: '%FLEET_API_TOKEN%'
    team_id: '%FLEET_TEAM_ID%'
    self_service: true
  Processor: FleetImporter
```

### Running a Recipe

```bash
# Run a single recipe
autopkg run GoogleChrome.fleet.recipe.yaml

# Run with verbose output
autopkg run -v GoogleChrome.fleet.recipe.yaml

# Override variables
autopkg run GoogleChrome.fleet.recipe.yaml \
  -k FLEET_API_BASE="https://fleet.example.com" \
  -k FLEET_API_TOKEN="your-token" \
  -k FLEET_TEAM_ID="1"
```

---

## Configuration

### Required Arguments

| Argument | Description |
|----------|-------------|
| \`pkg_path\` | Path to the built .pkg file (usually from parent recipe) |
| \`software_title\` | Human-readable software title (e.g., "Firefox.app") |
| \`version\` | Software version string |
| \`fleet_api_base\` | Fleet base URL (e.g., https://fleet.example.com) |
| \`fleet_api_token\` | Fleet API token with software management permissions |
| \`team_id\` | Fleet team ID to upload the package to |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| \`platform\` | \`darwin\` | Platform: darwin, windows, linux, ios, or ipados |
| \`self_service\` | \`true\` | Whether package is available for self-service installation |
| \`automatic_install\` | \`false\` | Auto-install on hosts without this software |
| \`labels_include_any\` | \`[]\` | List of label names - software available on hosts with ANY of these |
| \`labels_exclude_any\` | \`[]\` | List of label names - software excluded from hosts with ANY of these |
| \`install_script\` | \`""\` | Custom install script body |
| \`uninstall_script\` | \`""\` | Custom uninstall script body |
| \`pre_install_query\` | \`""\` | Pre-install osquery SQL condition |
| \`post_install_script\` | \`""\` | Post-install script body |

### Output Variables

| Variable | Description |
|----------|-------------|
| \`fleet_title_id\` | Fleet software title ID (may be None for duplicates) |
| \`fleet_installer_id\` | Fleet installer ID (may be None for duplicates) |
| \`hash_sha256\` | SHA-256 hash of uploaded package |

---

## Advanced Examples

### Self-Service Only for Specific Labels

```yaml
Process:
- Arguments:
    pkg_path: '%pkg_path%'
    software_title: '%NAME%'
    version: '%version%'
    fleet_api_base: '%FLEET_API_BASE%'
    fleet_api_token: '%FLEET_API_TOKEN%'
    team_id: '%FLEET_TEAM_ID%'
    self_service: true
    labels_include_any:
      - workstations
      - developers
  Processor: FleetImporter
```

### Automatic Installation with Exclusions

```yaml
Process:
- Arguments:
    pkg_path: '%pkg_path%'
    software_title: '%NAME%'
    version: '%version%'
    fleet_api_base: '%FLEET_API_BASE%'
    fleet_api_token: '%FLEET_API_TOKEN%'
    team_id: '%FLEET_TEAM_ID%'
    automatic_install: true
    labels_exclude_any:
      - servers
      - kiosk
  Processor: FleetImporter
```

### With Custom Scripts

```yaml
Process:
- Arguments:
    pkg_path: '%pkg_path%'
    software_title: '%NAME%'
    version: '%version%'
    fleet_api_base: '%FLEET_API_BASE%'
    fleet_api_token: '%FLEET_API_TOKEN%'
    team_id: '%FLEET_TEAM_ID%'
    self_service: true
    pre_install_query: 'SELECT 1 FROM apps WHERE bundle_id = "com.example.app" AND version < "2.0";'
    install_script: |
      #!/bin/bash
      # Custom installation logic
      echo "Installing..."
    post_install_script: |
      #!/bin/bash
      # Verify installation
      echo "Verifying..."
  Processor: FleetImporter
```

---

## Troubleshooting

### Package Already Exists

The processor uses a **two-layer detection strategy** to avoid uploading duplicates:

**Layer 1: Proactive Check (Before Upload)**

Before attempting upload, the processor queries Fleet's API to search for existing packages:

1. Searches for the software title using `/api/v1/fleet/software/titles`
2. Uses smart matching: exact match → case-insensitive → fuzzy match (e.g., "Zoom" matches "zoom.us")
3. Checks if the version exists in the software's `versions` array or `software_package` object
4. If found: Skips upload entirely, calculates hash from local file, exits gracefully

**Layer 2: Upload-Time Detection (Safety Net)**

If the proactive check misses something (network issue, timing, stale data), Fleet's API provides a fallback:

1. Fleet returns HTTP 409 Conflict when a duplicate package is uploaded
2. Processor catches the 409 error and exits gracefully
3. Calculates hash from local file and sets output variables

**Result:**

- Output variables: `fleet_title_id` and `fleet_installer_id` are set to `None`, `hash_sha256` contains the calculated hash
- No error is raised - this is expected idempotent behavior
- Running the same recipe multiple times is safe and won't create duplicates

**Note:** Fleet's API doesn't yet support hash-based lookups (tracked in [fleetdm/fleet#32965](https://github.com/fleetdm/fleet/issues/32965)), so the processor relies on title/version matching rather than content hash comparison.

### Version Detection Issues

The processor requires Fleet v4.74.0 or higher. If you see version-related errors:

```bash
# Check your Fleet version
curl -H "Authorization: Bearer $FLEET_API_TOKEN" \
  "$FLEET_API_BASE/api/v1/fleet/version"
```

### Authentication Errors

Ensure your Fleet API token has the required permissions:

- Read and write access to software management
- Access to the specified team

### Label Conflicts

Fleet's API only allows either \`labels_include_any\` OR \`labels_exclude_any\`, not both. If you specify both, the processor will fail with an error.

---

## Development

### Code Style

This processor follows AutoPkg's strict code style requirements:

```bash
# Validate Python syntax
python3 -m py_compile FleetImporter/FleetImporter.py

# Check formatting (Black)
python3 -m black --check FleetImporter/FleetImporter.py

# Check import sorting
python3 -m isort --check-only FleetImporter/FleetImporter.py

# Run linter
python3 -m flake8 FleetImporter/FleetImporter.py
```

All checks must pass before code can be contributed to AutoPkg repositories.

### Testing

Test the processor with a sample recipe:

```bash
# Create test environment
export FLEET_API_BASE="https://fleet.example.com"
export FLEET_API_TOKEN="your-test-token"
export FLEET_TEAM_ID="1"

# Run test recipe with verbose output
autopkg run -vv GoogleChrome.fleet.recipe.yaml
```

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure all code style checks pass
5. Submit a pull request

---

## License

See [LICENSE](LICENSE) file for details.

---

## Support

For issues or questions:

- Open an issue in this repository
- Review existing [issues](https://github.com/kitzy/fleetimporter/issues)
- Check the [AutoPkg discussion forums](https://github.com/autopkg/autopkg/discussions)

---

## Related Links

- [Fleet Documentation](https://fleetdm.com/docs)
- [Fleet Software Management API](https://fleetdm.com/docs/rest-api/rest-api#software)
- [AutoPkg Documentation](https://github.com/autopkg/autopkg/wiki)
- [AutoPkg Recipe Format](https://github.com/autopkg/autopkg/wiki/Recipe-Format)
