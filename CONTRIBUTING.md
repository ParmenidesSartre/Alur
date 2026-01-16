# Contributing to Alur Framework

Thank you for your interest in contributing to Alur! This document provides guidelines for contributing to the project.

## Table of Contents

- [Development Setup](#development-setup)
- [Git Workflow](#git-workflow)
- [Branch Naming](#branch-naming)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Code Standards](#code-standards)
- [Release Process](#release-process)

---

## Development Setup

### Prerequisites

- Python 3.8+
- Git
- Java 8 or 11 (for PySpark)
- AWS CLI (for deployment testing)
- Terraform (for infrastructure testing)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/ParmenidesSartre/Alur.git
cd Alur

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Verify installation
python -c "import alur; print(alur.__version__)"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=alur --cov-report=html

# Run specific test file
pytest tests/test_core.py
```

---

## Git Workflow

### Branch Strategy

We use a simplified Git Flow:

```
main (production-ready)
  │
  ├── feature/xxx (new features)
  ├── fix/xxx (bug fixes)
  ├── docs/xxx (documentation)
  └── refactor/xxx (code improvements)
```

### Standard Development Flow

```bash
# 1. Start from main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/add-kafka-connector

# 3. Make changes and commit
git add .
git commit -m "feat: add Kafka connector for streaming ingestion"

# 4. Push to remote
git push origin feature/add-kafka-connector

# 5. Create Pull Request on GitHub

# 6. After PR is merged, clean up
git checkout main
git pull origin main
git branch -d feature/add-kafka-connector
```

### Keeping Branch Updated

```bash
# While on feature branch, sync with main
git fetch origin
git rebase origin/main

# If conflicts, resolve them then:
git add .
git rebase --continue
```

---

## Branch Naming

Use prefixes to categorize branches:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New functionality | `feature/add-kafka-connector` |
| `fix/` | Bug fixes | `fix/parquet-timestamp-issue` |
| `docs/` | Documentation only | `docs/update-readme` |
| `refactor/` | Code restructuring | `refactor/simplify-runner` |
| `test/` | Test additions | `test/add-quality-tests` |
| `chore/` | Maintenance tasks | `chore/update-dependencies` |

**Rules:**
- Use lowercase
- Use hyphens (not underscores)
- Keep it short but descriptive
- Include issue number if applicable: `fix/123-null-pointer`

---

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

### Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Formatting (no code change) |
| `refactor` | Code restructuring |
| `test` | Adding tests |
| `chore` | Maintenance tasks |
| `perf` | Performance improvements |

### Examples

```bash
# Feature
git commit -m "feat(ingestion): add Kafka connector for streaming data"

# Bug fix
git commit -m "fix(runner): handle null values in partition columns"

# Documentation
git commit -m "docs: update installation instructions for Windows"

# Breaking change
git commit -m "feat(core)!: rename BronzeTable to RawTable

BREAKING CHANGE: BronzeTable class renamed to RawTable.
Update imports: from alur import RawTable"
```

### Rules

1. **Subject line**: Max 50 characters, imperative mood ("add" not "added")
2. **Body**: Explain *what* and *why*, not *how*
3. **Footer**: Reference issues (`Fixes #123`)

---

## Pull Request Process

### Before Creating PR

1. **Rebase on main**: Ensure your branch is up to date
2. **Run tests**: All tests must pass
3. **Lint code**: Run `black` and `isort`
4. **Update docs**: If adding features, update relevant docs

### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added for new features

## Checklist
- [ ] Code follows project style
- [ ] Self-reviewed my code
- [ ] Updated documentation
- [ ] No new warnings
```

### Review Process

1. At least 1 approval required
2. All CI checks must pass
3. No unresolved comments
4. Squash merge to main

---

## Code Standards

### Python Style

- Follow PEP 8
- Use Black for formatting (line length 88)
- Use isort for import sorting
- Type hints encouraged

```bash
# Format code
black src/
isort src/

# Check types
mypy src/alur/
```

### Project Structure

```
Alur/
├── src/alur/           # Main package
│   ├── core/           # Table definitions, fields
│   ├── decorators/     # @pipeline decorator
│   ├── engine/         # Runners, adapters
│   ├── infra/          # Terraform generation
│   ├── ingestion/      # Bronze helpers
│   ├── quality/        # @expect decorator
│   ├── scheduling/     # @schedule decorator
│   └── templates/      # Project templates
├── tests/              # Test files
├── examples/           # Example code
└── docs/               # Documentation
```

### Naming Conventions

- **Classes**: PascalCase (`BronzeTable`, `PipelineRunner`)
- **Functions**: snake_case (`add_bronze_metadata`, `run_pipeline`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_TIMEOUT`)
- **Files**: snake_case (`pipeline_runner.py`)

---

## Release Process

### Versioning

We use [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, backward compatible

### Creating a Release

```bash
# 1. Update version in pyproject.toml and __init__.py
# 2. Update CHANGELOG.md

# 3. Commit version bump
git add .
git commit -m "chore: bump version to X.Y.Z"

# 4. Create tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# 5. Push
git push origin main
git push origin vX.Y.Z

# 6. Create GitHub Release from tag
```

### Changelog Format

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Vulnerability fixes
```

---

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/ParmenidesSartre/Alur/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ParmenidesSartre/Alur/discussions)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
