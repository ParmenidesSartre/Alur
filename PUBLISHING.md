# Publishing Alur to PyPI

This guide covers how to publish Alur Framework to PyPI (Python Package Index).

## Table of Contents

- [Prerequisites](#prerequisites)
- [Manual Publishing](#manual-publishing)
- [Automated Publishing (GitHub Actions)](#automated-publishing-github-actions)
- [TestPyPI (Testing)](#testpypi-testing)
- [Version Management](#version-management)
- [Post-Release Checklist](#post-release-checklist)

## Prerequisites

### 1. PyPI Account

Create accounts on:
- **PyPI (Production):** https://pypi.org/account/register/
- **TestPyPI (Testing):** https://test.pypi.org/account/register/

### 2. API Tokens

Create API tokens for secure authentication:

**PyPI:**
1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name: `alur-framework-publishing`
4. Scope: Select "Entire account" (or specific project after first publish)
5. Copy the token (starts with `pypi-`)

**TestPyPI:**
1. Go to https://test.pypi.org/manage/account/token/
2. Same steps as above

**Store tokens securely:**
```bash
# Create ~/.pypirc file
nano ~/.pypirc
```

```ini
[pypi]
  username = __token__
  password = pypi-YOUR-PYPI-TOKEN-HERE

[testpypi]
  username = __token__
  password = pypi-YOUR-TESTPYPI-TOKEN-HERE
```

```bash
# Secure the file
chmod 600 ~/.pypirc
```

### 3. Install Build Tools

```bash
pip install --upgrade build twine
```

## Manual Publishing

### Step 1: Update Version

Version is managed in 3 places (should match):
- `pyproject.toml` - line 7: `version = "0.7.0"`
- `src/alur/__init__.py` - line 78: `__version__ = "0.7.0"`
- `README.md` - line 405: `**Current Version:** 0.7.0`
- `CHANGELOG.md` - Add entry for new version

### Step 2: Clean Previous Builds

```bash
# Remove old build artifacts
rm -rf dist/ build/ *.egg-info src/*.egg-info
```

### Step 3: Build Package

```bash
# Build wheel and source distribution
python -m build
```

This creates:
- `dist/alur_framework-0.7.0-py3-none-any.whl` (wheel)
- `dist/alur-framework-0.7.0.tar.gz` (source)

### Step 4: Verify Build

```bash
# Check package metadata
twine check dist/*
```

Expected output:
```
Checking dist/alur_framework-0.7.0-py3-none-any.whl: PASSED
Checking dist/alur-framework-0.7.0.tar.gz: PASSED
```

### Step 5: Test Installation Locally

```bash
# Create test environment
python -m venv test_env
source test_env/bin/activate  # Windows: test_env\Scripts\activate

# Install from wheel
pip install dist/alur_framework-0.7.0-py3-none-any.whl

# Test import
python -c "from alur import schedule, pipeline; print('OK')"

# Test CLI
alur --version

# Cleanup
deactivate
rm -rf test_env
```

### Step 6: Upload to PyPI

**Option A: Upload to TestPyPI (Recommended First)**

```bash
twine upload --repository testpypi dist/*
```

Verify at: https://test.pypi.org/project/alur-framework/

Test installation from TestPyPI:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ alur-framework
```

**Option B: Upload to Production PyPI**

```bash
twine upload dist/*
```

Verify at: https://pypi.org/project/alur-framework/

### Step 7: Verify Production Installation

```bash
# In a fresh environment
pip install alur-framework

# Test
python -c "from alur import schedule, pipeline; print('OK')"
alur --version
```

## Automated Publishing (GitHub Actions)

### Option 1: Automatic on Git Tag

Create `.github/workflows/publish-pypi.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*'  # Trigger on version tags (v0.7.0, v1.0.0, etc.)

jobs:
  publish:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        run: python -m build

      - name: Check package
        run: twine check dist/*

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

**Usage:**
```bash
# Tag a release
git tag -a v0.7.0 -m "Release v0.7.0: Pipeline Scheduling"
git push origin v0.7.0

# GitHub Actions automatically builds and publishes
```

### Option 2: Manual Trigger via GitHub Actions

Create `.github/workflows/publish-pypi-manual.yml`:

```yaml
name: Publish to PyPI (Manual)

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'PyPI environment'
        required: true
        type: choice
        options:
          - testpypi
          - pypi

jobs:
  publish:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        run: python -m build

      - name: Check package
        run: twine check dist/*

      - name: Publish to TestPyPI
        if: ${{ github.event.inputs.environment == 'testpypi' }}
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.TESTPYPI_API_TOKEN }}
        run: twine upload --repository testpypi dist/*

      - name: Publish to PyPI
        if: ${{ github.event.inputs.environment == 'pypi' }}
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

**Setup GitHub Secrets:**
1. Go to GitHub repo → Settings → Secrets and variables → Actions
2. Add secrets:
   - `PYPI_API_TOKEN` - Your PyPI token
   - `TESTPYPI_API_TOKEN` - Your TestPyPI token

**Usage:**
1. Go to Actions tab on GitHub
2. Select "Publish to PyPI (Manual)"
3. Click "Run workflow"
4. Choose `testpypi` or `pypi`

## TestPyPI (Testing)

Always test on TestPyPI before production:

### Upload to TestPyPI

```bash
twine upload --repository testpypi dist/*
```

### Install from TestPyPI

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ alur-framework
```

**Note:** `--extra-index-url https://pypi.org/simple/` is needed because dependencies (boto3, click, etc.) are not on TestPyPI.

### Verify TestPyPI Package

- URL: https://test.pypi.org/project/alur-framework/
- Check: README renders correctly
- Check: Version number is correct
- Check: Links work

## Version Management

### Semantic Versioning

Alur follows [Semantic Versioning](https://semver.org/):

- **MAJOR.MINOR.PATCH** (e.g., `0.7.0`)
- **MAJOR:** Breaking changes
- **MINOR:** New features (backwards-compatible)
- **PATCH:** Bug fixes (backwards-compatible)

### Release Checklist

Before releasing version `X.Y.Z`:

- [ ] Update version in `pyproject.toml`
- [ ] Update version in `src/alur/__init__.py`
- [ ] Update version in `README.md`
- [ ] Add entry to `CHANGELOG.md`
- [ ] Commit changes: `git commit -m "chore: bump version to vX.Y.Z"`
- [ ] Tag release: `git tag -a vX.Y.Z -m "Release vX.Y.Z: <description>"`
- [ ] Push: `git push && git push --tags`
- [ ] Build and test locally
- [ ] Upload to TestPyPI and test
- [ ] Upload to PyPI
- [ ] Create GitHub Release with notes

## Post-Release Checklist

After publishing to PyPI:

### 1. Create GitHub Release

1. Go to https://github.com/ParmenidesSartre/Alur/releases/new
2. Select tag: `v0.7.0`
3. Title: `v0.7.0: Pipeline Scheduling`
4. Description: Copy from `CHANGELOG.md`
5. Publish release

### 2. Verify Installation

```bash
# Test in clean environment
python -m venv test_release
source test_release/bin/activate
pip install alur-framework

# Verify
alur --version  # Should show 0.7.0
python -c "from alur import schedule; print('OK')"

deactivate
rm -rf test_release
```

### 3. Update Documentation Links

If using ReadTheDocs or GitHub Pages, ensure version is updated.

### 4. Announce Release

- Twitter/LinkedIn
- GitHub Discussions
- Reddit (r/Python, r/dataengineering)
- Dev.to / Medium blog post

## Troubleshooting

### Error: "File already exists"

**Problem:** Trying to upload same version twice.

**Solution:** Increment version number. PyPI doesn't allow overwriting.

### Error: "Invalid distribution filename"

**Problem:** Package name mismatch.

**Solution:** Ensure `pyproject.toml` has `name = "alur-framework"` (with hyphen).

### Error: "Uploading to TestPyPI fails"

**Problem:** TestPyPI has stricter requirements.

**Solution:** Check that `README.md` renders correctly as markdown.

### README not rendering on PyPI

**Problem:** PyPI uses CommonMark, not full Markdown.

**Solution:**
- Avoid GitHub-specific syntax
- Use standard markdown tables
- Test with: `python -m readme_renderer README.md`

### CLI command not found after install

**Problem:** `alur` command not in PATH.

**Solution:** Check `[project.scripts]` in `pyproject.toml`:
```toml
[project.scripts]
alur = "alur.cli:main"
```

## Useful Commands

```bash
# Check package metadata
twine check dist/*

# View package contents
tar -tzf dist/alur-framework-0.7.0.tar.gz
unzip -l dist/alur_framework-0.7.0-py3-none-any.whl

# Test README rendering
python -m pip install readme-renderer
python -m readme_renderer README.md

# Check PyPI statistics
# Visit: https://pypistats.org/packages/alur-framework
```

## Resources

- **PyPI:** https://pypi.org/
- **TestPyPI:** https://test.pypi.org/
- **Python Packaging Guide:** https://packaging.python.org/
- **Twine Documentation:** https://twine.readthedocs.io/
- **Semantic Versioning:** https://semver.org/
