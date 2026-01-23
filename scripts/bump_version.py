#!/usr/bin/env python3
"""
Version Bumping Script for Alur Framework

Automatically updates version numbers across all project files.

Usage:
    python scripts/bump_version.py 0.8.0
    python scripts/bump_version.py 0.7.1 --dry-run
"""

import argparse
import re
import sys
from pathlib import Path
from datetime import date


# Files to update with their patterns
VERSION_FILES = {
    "pyproject.toml": [
        (r'^version = "[^"]+"', 'version = "{version}"'),  # Must be at line start
    ],
    "src/alur/__init__.py": [
        (r'__version__ = "[^"]+"', '__version__ = "{version}"'),
    ],
    "README.md": [
        (r'\*\*Current Version:\*\* [0-9.]+', '**Current Version:** {version}'),
        (r'\(Released \d{4}-\d{2}-\d{2}\)', '(Released {date})'),
    ],
    "docs/index.md": [
        (r'version-[0-9.]+-blue', 'version-{version}-blue'),
    ],
}


def get_current_version():
    """Read current version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found. Run from project root.")
        sys.exit(1)

    content = pyproject_path.read_text(encoding='utf-8')
    match = re.search(r'version = "([^"]+)"', content)
    if match:
        return match.group(1)

    print("Error: Could not find version in pyproject.toml")
    sys.exit(1)


def validate_version(version):
    """Validate semantic version format."""
    pattern = r'^\d+\.\d+\.\d+$'
    if not re.match(pattern, version):
        print(f"Error: Invalid version format '{version}'")
        print("Expected format: MAJOR.MINOR.PATCH (e.g., 0.8.0)")
        sys.exit(1)


def update_file(filepath, patterns, new_version, current_date, dry_run=False):
    """Update version in a single file."""
    path = Path(filepath)
    if not path.exists():
        print(f"Warning: {filepath} not found, skipping")
        return False

    content = path.read_text(encoding='utf-8')
    original_content = content

    # Apply all patterns
    for pattern, replacement in patterns:
        replacement_str = replacement.format(version=new_version, date=current_date)
        content = re.sub(pattern, replacement_str, content, flags=re.MULTILINE)

    # Check if anything changed
    if content == original_content:
        print(f"  {filepath}: No changes needed")
        return False

    if dry_run:
        print(f"  {filepath}: Would update")
        # Show diff
        for i, (old_line, new_line) in enumerate(zip(original_content.split('\n'), content.split('\n'))):
            if old_line != new_line:
                print(f"    - {old_line}")
                print(f"    + {new_line}")
    else:
        path.write_text(content, encoding='utf-8')
        print(f"  {filepath}: Updated")

    return True


def add_changelog_entry(new_version, current_date, dry_run=False):
    """Add new version entry to CHANGELOG.md."""
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        print("Warning: CHANGELOG.md not found, skipping")
        return False

    content = changelog_path.read_text(encoding='utf-8')

    # Check if version already exists
    if f"## [{new_version}]" in content:
        print(f"  CHANGELOG.md: Version {new_version} already exists")
        return False

    # Template for new version
    new_entry = f"""## [{new_version}] - {current_date}

### Added
-

### Changed
-

### Fixed
-

"""

    # Insert after the header (after "## [PREVIOUS_VERSION]")
    lines = content.split('\n')
    insert_index = None
    for i, line in enumerate(lines):
        if line.startswith('## ['):
            insert_index = i
            break

    if insert_index is None:
        print("Warning: Could not find insertion point in CHANGELOG.md")
        return False

    # Insert new entry
    lines.insert(insert_index, new_entry.rstrip())
    new_content = '\n'.join(lines)

    if dry_run:
        print(f"  CHANGELOG.md: Would add entry for {new_version}")
        print(f"\n{new_entry}")
    else:
        changelog_path.write_text(new_content, encoding='utf-8')
        print(f"  CHANGELOG.md: Added entry for {new_version}")
        print(f"    Don't forget to fill in the changes!")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Bump version across all Alur Framework files"
    )
    parser.add_argument(
        "version",
        help="New version number (e.g., 0.8.0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    parser.add_argument(
        "--skip-changelog",
        action="store_true",
        help="Skip adding CHANGELOG.md entry"
    )

    args = parser.parse_args()

    # Validate new version
    new_version = args.version
    validate_version(new_version)

    # Get current version
    current_version = get_current_version()
    current_date = date.today().strftime('%Y-%m-%d')

    print("=" * 60)
    print("Alur Framework Version Bump")
    print("=" * 60)
    print(f"Current version: {current_version}")
    print(f"New version:     {new_version}")
    print(f"Date:            {current_date}")
    if args.dry_run:
        print("\nDRY RUN MODE - No files will be modified")
    print("=" * 60)
    print()

    # Check if version is actually changing
    if current_version == new_version:
        print(f"Warning: Version is already {new_version}")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted")
            sys.exit(0)

    # Update all files
    updated_count = 0
    print("Updating files:")

    for filepath, patterns in VERSION_FILES.items():
        if update_file(filepath, patterns, new_version, current_date, args.dry_run):
            updated_count += 1

    # Add changelog entry
    if not args.skip_changelog:
        print()
        if add_changelog_entry(new_version, current_date, args.dry_run):
            updated_count += 1

    print()
    print("=" * 60)
    if args.dry_run:
        print(f"Would update {updated_count} file(s)")
        print("\nRun without --dry-run to apply changes")
    else:
        print(f"Successfully updated {updated_count} file(s) to version {new_version}")
        print("\nNext steps:")
        print(f"  1. Review CHANGELOG.md and fill in the changes")
        print(f"  2. Commit: git add . && git commit -m 'chore: bump version to v{new_version}'")
        print(f"  3. Tag: git tag -a v{new_version} -m 'Release v{new_version}: Description'")
        print(f"  4. Push: git push origin main && git push origin v{new_version}")
    print("=" * 60)


if __name__ == "__main__":
    main()
