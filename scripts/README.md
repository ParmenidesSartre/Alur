# Release Scripts

Automated scripts for releasing new versions of Alur Framework.

## Quick Start

### Automated Release (Recommended)

**Windows:**
```bash
scripts\release.bat 0.8.0 "Silver Layer Support"
```

**Linux/Mac:**
```bash
./scripts/release.sh 0.8.0 "Silver Layer Support"
```

This automatically:
1. Validates git status
2. Updates all version numbers
3. Adds CHANGELOG entry
4. Commits changes
5. Creates and pushes git tag
6. Triggers GitHub Actions to publish to PyPI

---

## Scripts

### `bump_version.py` - Version Bumping

Updates version numbers across all project files.

**Usage:**
```bash
# Bump to new version
python scripts/bump_version.py 0.8.0

# Dry run (see changes without applying)
python scripts/bump_version.py 0.8.0 --dry-run

# Skip CHANGELOG entry
python scripts/bump_version.py 0.8.0 --skip-changelog
```

**Files Updated:**
- `pyproject.toml` - Package version
- `src/alur/__init__.py` - Module version
- `README.md` - Current version badge and release date
- `docs/index.md` - Version badge
- `CHANGELOG.md` - Adds new version entry (optional)

**Example:**
```bash
# See what would change
python scripts/bump_version.py 0.8.0 --dry-run

# Apply changes
python scripts/bump_version.py 0.8.0
```

**Output:**
```
============================================================
Alur Framework Version Bump
============================================================
Current version: 0.7.1
New version:     0.8.0
Date:            2026-01-25
============================================================

Updating files:
  pyproject.toml: Updated
  src/alur/__init__.py: Updated
  README.md: Updated
  docs/index.md: Updated

  CHANGELOG.md: Added entry for 0.8.0
    Don't forget to fill in the changes!

============================================================
Successfully updated 5 file(s) to version 0.8.0

Next steps:
  1. Review CHANGELOG.md and fill in the changes
  2. Commit: git add . && git commit -m 'chore: bump version to v0.8.0'
  3. Tag: git tag -a v0.8.0 -m 'Release v0.8.0: Description'
  4. Push: git push origin main && git push origin v0.8.0
============================================================
```

---

### `release.bat` / `release.sh` - Full Release Automation

Complete release workflow: bump version → commit → tag → push.

**Usage:**
```bash
# Windows
scripts\release.bat <version> "<description>"
scripts\release.bat 0.8.0 "Silver Layer Support"

# Linux/Mac
./scripts/release.sh <version> "<description>"
./scripts/release.sh 0.8.0 "Silver Layer Support"
```

**What It Does:**
1. **Validates** - Checks for uncommitted changes
2. **Bumps version** - Updates all files via `bump_version.py`
3. **Commits** - Commits version bump with message `chore: bump version to vX.Y.Z`
4. **Pushes** - Pushes to main branch
5. **Tags** - Creates annotated git tag `vX.Y.Z`
6. **Triggers CI** - Pushing tag triggers GitHub Actions to publish to PyPI

**Example:**
```bash
> scripts\release.bat 0.8.0 "Silver Layer Support"

====================================
Alur Framework Release Script
====================================

Version: 0.8.0
Tag: v0.8.0
Description: Silver Layer Support

Continue with release? (y/n): y

Step 1/5: Checking git status...
OK: Working directory clean

Step 2/5: Bumping version numbers...
Successfully updated 5 file(s) to version 0.8.0

Step 3/5: Committing version bump...
OK: Version bump committed

Step 4/5: Pushing to main...
OK: Pushed to main

Step 5/5: Creating and pushing tag...
OK: Tag v0.8.0 pushed to GitHub

====================================
Release v0.8.0 initiated!
====================================

Next steps:
1. Monitor GitHub Actions: https://github.com/ParmenidesSartre/Alur/actions
2. Verify PyPI: https://pypi.org/project/alur-framework/0.8.0/
3. Create GitHub Release: https://github.com/ParmenidesSartre/Alur/releases/new?tag=v0.8.0
```

---

## Manual Version Bump

If you want more control:

### Step 1: Bump Version
```bash
python scripts/bump_version.py 0.8.0
```

### Step 2: Edit CHANGELOG.md
Fill in the changes for the new version:
```markdown
## [0.8.0] - 2026-01-25

### Added
- Silver layer with Apache Iceberg support
- Schema evolution capabilities

### Changed
- Updated data quality checks for Iceberg tables

### Fixed
- Fixed timestamp handling in bronze ingestion
```

### Step 3: Commit and Tag
```bash
git add .
git commit -m "chore: bump version to v0.8.0"
git push origin main

git tag -a v0.8.0 -m "Release v0.8.0: Silver Layer Support"
git push origin v0.8.0
```

---

## Version Number Guidelines

Alur follows [Semantic Versioning](https://semver.org/):

**Format:** `MAJOR.MINOR.PATCH`

- **MAJOR** (0.x.x → 1.x.x) - Breaking changes
  - API changes that require code updates
  - Example: Rename `@pipeline` to `@transform`

- **MINOR** (0.7.x → 0.8.x) - New features (backward-compatible)
  - Add new decorators, commands, or capabilities
  - Example: Add Silver/Gold layer support

- **PATCH** (0.7.0 → 0.7.1) - Bug fixes (backward-compatible)
  - Fix bugs, update docs, improve error messages
  - Example: Fix schema validation error

**Examples:**
- `0.7.1` - Patch: Fix .gitignore
- `0.8.0` - Minor: Add Silver layer
- `1.0.0` - Major: First stable release

---

## Troubleshooting

### "Working directory has uncommitted changes"

**Problem:** You have uncommitted files.

**Solution:**
```bash
# Check what's uncommitted
git status

# Commit or stash changes
git add .
git commit -m "Your changes"

# Then retry release
```

### "Version is already X.Y.Z"

**Problem:** Target version already exists.

**Solution:** Choose a different version number (increment further).

### "python: command not found" (Linux/Mac)

**Problem:** Python not in PATH.

**Solution:**
```bash
# Use python3 instead
sed -i 's/python scripts/python3 scripts/' scripts/release.sh

# Or install Python
sudo apt install python3  # Ubuntu
brew install python3      # macOS
```

### "Version bump failed"

**Problem:** `bump_version.py` encountered an error.

**Solution:**
```bash
# Run manually to see full error
python scripts/bump_version.py 0.8.0

# Common issues:
# - Invalid version format (must be X.Y.Z)
# - File not found (run from project root)
```

---

## CI/CD Integration

### GitHub Actions

Pushing a tag automatically triggers:
- **Workflow:** `.github/workflows/publish-pypi.yml`
- **Triggers on:** Tags matching `v*` (e.g., v0.8.0)
- **Actions:**
  1. Checkout code
  2. Build package (`python -m build`)
  3. Check package (`twine check dist/*`)
  4. Upload to PyPI (`twine upload dist/*`)

**Requirements:**
- GitHub Secret: `PYPI_API_TOKEN` must be configured
- See: [PUBLISHING.md](../PUBLISHING.md) for setup instructions

**Monitor:**
- https://github.com/ParmenidesSartre/Alur/actions

---

## Files

| File | Purpose |
|------|---------|
| `bump_version.py` | Cross-platform version bumping script |
| `release.bat` | Windows automated release |
| `release.sh` | Linux/Mac automated release |
| `README.md` | This file (documentation) |

---

## Tips

1. **Always use automated scripts** - Prevents forgetting to update version in some files

2. **Test with dry-run first:**
   ```bash
   python scripts/bump_version.py 0.8.0 --dry-run
   ```

3. **Fill in CHANGELOG before tagging:**
   - Script adds template entry
   - Fill in actual changes before committing

4. **Use semantic versioning:**
   - Breaking change → bump MAJOR
   - New feature → bump MINOR
   - Bug fix → bump PATCH

5. **Tag after CHANGELOG is complete:**
   - Don't rush the tag
   - Review changes first

---

For more information, see [RELEASE_WORKFLOW.md](../RELEASE_WORKFLOW.md).
