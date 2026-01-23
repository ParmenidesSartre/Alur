# Release Workflow for Alur Framework

This guide explains how to release a new version to PyPI and GitHub.

## Quick Reference

```bash
# 1. Update version everywhere
# 2. Commit changes
# 3. Tag release
git tag -a v0.8.0 -m "Release v0.8.0: Description"
git push origin v0.8.0
# 4. GitHub Actions automatically publishes to PyPI
```

## Complete Release Process

### Step 1: Update Version Numbers

When releasing version `X.Y.Z`, update in **3 files**:

#### File 1: `pyproject.toml` (line 7)
```toml
[project]
name = "alur-framework"
version = "0.8.0"  # ← Update this
```

#### File 2: `src/alur/__init__.py` (line 78)
```python
__version__ = "0.8.0"  # ← Update this
```

#### File 3: `CHANGELOG.md` (top)
Add new version entry:
```markdown
## [0.8.0] - 2026-01-25

### Added
- New feature description

### Changed
- Changes description

### Fixed
- Bug fixes
```

### Step 2: Commit Version Changes

```bash
cd C:\Users\USER\Desktop\Alur

# Commit version bump
git add pyproject.toml src/alur/__init__.py CHANGELOG.md
git commit -m "chore: bump version to v0.8.0"
git push origin main
```

### Step 3: Create and Push Git Tag

```bash
# Create annotated tag
git tag -a v0.8.0 -m "Release v0.8.0: Silver Layer Support"

# Push tag to GitHub
git push origin v0.8.0
```

**That's it!** GitHub Actions automatically:
1. Builds the package
2. Runs `twine check`
3. Uploads to PyPI

Monitor at: https://github.com/ParmenidesSartre/Alur/actions

### Step 4: Create GitHub Release (Optional)

1. Go to: https://github.com/ParmenidesSartre/Alur/releases/new
2. Select tag: `v0.8.0`
3. Title: `v0.8.0: Silver Layer Support`
4. Description: Copy from `CHANGELOG.md`
5. Click "Publish release"

## Automated Publishing (Current Setup)

Your repository has `.github/workflows/publish-pypi.yml` which:
- Triggers on: `v*` tags (e.g., v0.8.0, v1.0.0)
- Builds package automatically
- Publishes to PyPI using `PYPI_API_TOKEN` secret

### Setup GitHub Secret (One-Time)

If not already done:

1. **Generate new PyPI token** (security best practice):
   - Go to: https://pypi.org/manage/account/token/
   - Click "Add API token"
   - Name: `alur-github-actions`
   - Scope: Project → `alur-framework`
   - Copy token (starts with `pypi-...`)

2. **Add to GitHub Secrets**:
   - Go to: https://github.com/ParmenidesSartre/Alur/settings/secrets/actions
   - Click "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Value: Paste your token
   - Click "Add secret"

3. **Test the workflow**:
   ```bash
   git tag -a v0.7.1 -m "Test release"
   git push origin v0.7.1
   ```

   Check: https://github.com/ParmenidesSartre/Alur/actions

## Manual Publishing (Alternative)

If you prefer manual control:

```bash
# 1. Clean previous builds
rm -rf dist/ build/ *.egg-info src/*.egg-info

# 2. Build package
python -m build

# 3. Check package
twine check dist/*

# 4. Upload to PyPI
twine upload dist/*
# Enter: __token__
# Enter: pypi-YOUR-TOKEN-HERE
```

## Version Numbering Guide

Alur follows **Semantic Versioning** (https://semver.org/):

### Format: MAJOR.MINOR.PATCH

- **MAJOR** (0.x.x → 1.x.x): Breaking changes
  - Example: Change decorator API, remove features
  - Users need to modify their code

- **MINOR** (0.7.x → 0.8.x): New features (backward-compatible)
  - Example: Add @transform decorator, new CLI command
  - Users can upgrade without code changes

- **PATCH** (0.7.0 → 0.7.1): Bug fixes (backward-compatible)
  - Example: Fix schema validation bug, correct CLI help text
  - Users should upgrade immediately

### Examples:
- `0.7.0` → `0.7.1`: Bug fix release
- `0.7.0` → `0.8.0`: Add Silver/Gold layers
- `0.9.0` → `1.0.0`: First stable release (production-ready)

## Release Checklist

Before creating a release tag:

- [ ] Update version in `pyproject.toml`
- [ ] Update version in `src/alur/__init__.py`
- [ ] Update `CHANGELOG.md` with new entry
- [ ] Update `README.md` if needed (current version)
- [ ] All tests pass locally
- [ ] Feature branch merged to `main`
- [ ] Commit version bump: `git commit -m "chore: bump version to vX.Y.Z"`
- [ ] Push to main: `git push origin main`
- [ ] Create tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z: Description"`
- [ ] Push tag: `git push origin vX.Y.Z`
- [ ] Monitor GitHub Actions workflow
- [ ] Verify on PyPI: https://pypi.org/project/alur-framework/
- [ ] Create GitHub Release with notes
- [ ] Test installation: `pip install alur-framework==X.Y.Z`

## Verify Published Package

After GitHub Actions completes:

```bash
# Check PyPI
# Visit: https://pypi.org/project/alur-framework/

# Test installation in clean environment
python -m venv test_env
source test_env/bin/activate  # Windows: test_env\Scripts\activate
pip install alur-framework==0.8.0
alur --version
python -c "import alur; print(alur.__version__)"
deactivate
rm -rf test_env
```

## Troubleshooting

### Problem: GitHub Actions Fails

**Check:**
1. Is `PYPI_API_TOKEN` secret configured?
   - Go to: https://github.com/ParmenidesSartre/Alur/settings/secrets/actions
2. Is token still valid?
   - PyPI tokens don't expire, but can be revoked
3. Check workflow logs:
   - https://github.com/ParmenidesSartre/Alur/actions

### Problem: "File already exists" on PyPI

**Cause:** Tried to upload same version twice.

**Solution:**
- PyPI doesn't allow overwriting versions
- Increment version number (e.g., 0.8.0 → 0.8.1)
- Delete and recreate git tag:
  ```bash
  git tag -d v0.8.0
  git push origin :refs/tags/v0.8.0
  git tag -a v0.8.1 -m "Release v0.8.1"
  git push origin v0.8.1
  ```

### Problem: Wrong version published

**Solution:**
- Can't delete/modify PyPI versions
- Must publish new version (e.g., 0.8.0 → 0.8.1)
- Mark old version as "yanked" on PyPI:
  1. Go to: https://pypi.org/manage/project/alur-framework/releases/
  2. Select version
  3. Click "Yank version"
  4. Users won't install it by default

### Problem: Forgot to update version

**Solution:**
```bash
# Delete the tag locally and remotely
git tag -d v0.8.0
git push origin :refs/tags/v0.8.0

# Update version numbers
# Edit: pyproject.toml, src/alur/__init__.py, CHANGELOG.md

# Commit
git add .
git commit -m "fix: correct version to 0.8.0"
git push origin main

# Recreate tag
git tag -a v0.8.0 -m "Release v0.8.0: Description"
git push origin v0.8.0
```

## Example: Full Release for v0.8.0

```bash
# 1. Switch to main branch
git checkout main
git pull

# 2. Create feature branch (if not already)
git checkout -b feature/silver-layer

# ... make changes ...

# 3. Commit feature
git add .
git commit -m "feat: add silver layer with Iceberg support"
git push origin feature/silver-layer

# 4. Merge to main (via PR or directly)
git checkout main
git merge feature/silver-layer
git push origin main

# 5. Update versions
# Edit: pyproject.toml → version = "0.8.0"
# Edit: src/alur/__init__.py → __version__ = "0.8.0"
# Edit: CHANGELOG.md → Add [0.8.0] section

git add pyproject.toml src/alur/__init__.py CHANGELOG.md
git commit -m "chore: bump version to v0.8.0"
git push origin main

# 6. Tag and release
git tag -a v0.8.0 -m "Release v0.8.0: Silver Layer with Apache Iceberg"
git push origin v0.8.0

# 7. GitHub Actions automatically publishes to PyPI
# Monitor: https://github.com/ParmenidesSartre/Alur/actions

# 8. Verify
# Visit: https://pypi.org/project/alur-framework/0.8.0/
pip install alur-framework==0.8.0
python -c "import alur; print(alur.__version__)"  # Should print: 0.8.0

# 9. Create GitHub Release
# Go to: https://github.com/ParmenidesSartre/Alur/releases/new
# Tag: v0.8.0
# Title: v0.8.0: Silver Layer with Apache Iceberg
# Description: [Copy from CHANGELOG.md]
```

## Tips

1. **Test on TestPyPI first** (for major releases):
   ```bash
   twine upload --repository testpypi dist/*
   pip install --index-url https://test.pypi.org/simple/ alur-framework
   ```

2. **Use annotated tags** (not lightweight):
   - ✅ Good: `git tag -a v0.8.0 -m "Release v0.8.0"`
   - ❌ Bad: `git tag v0.8.0`

3. **Keep consistent versioning**:
   - Always `vX.Y.Z` format for tags
   - Always `X.Y.Z` format in code

4. **Pre-release versions** (optional):
   - Alpha: `0.8.0a1`
   - Beta: `0.8.0b1`
   - Release Candidate: `0.8.0rc1`

## Resources

- **GitHub Actions Workflow:** `.github/workflows/publish-pypi.yml`
- **Package Config:** `pyproject.toml`
- **Publishing Guide:** `PUBLISHING.md`
- **Semantic Versioning:** https://semver.org/
- **PyPI Project:** https://pypi.org/project/alur-framework/
- **GitHub Releases:** https://github.com/ParmenidesSartre/Alur/releases
