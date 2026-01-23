#!/bin/bash
# Quick release script for Alur Framework
# Usage: ./scripts/release.sh 0.8.0 "Silver Layer Support"

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 2 ]; then
    echo -e "${RED}Error: Missing arguments${NC}"
    echo "Usage: ./scripts/release.sh <version> <description>"
    echo "Example: ./scripts/release.sh 0.8.0 'Silver Layer Support'"
    exit 1
fi

VERSION=$1
DESCRIPTION=$2
TAG="v${VERSION}"

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}Alur Framework Release Script${NC}"
echo -e "${GREEN}====================================${NC}"
echo ""
echo "Version: ${VERSION}"
echo "Tag: ${TAG}"
echo "Description: ${DESCRIPTION}"
echo ""

# Confirm
read -p "Continue with release? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Release cancelled${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 1/6: Checking git status...${NC}"
if [[ -n $(git status -s) ]]; then
    echo -e "${RED}Error: Working directory has uncommitted changes${NC}"
    git status -s
    exit 1
fi
echo -e "${GREEN}✓ Working directory clean${NC}"

echo ""
echo -e "${YELLOW}Step 2/6: Updating version numbers...${NC}"

# Update pyproject.toml
sed -i.bak "s/^version = .*/version = \"${VERSION}\"/" pyproject.toml
rm -f pyproject.toml.bak
echo -e "${GREEN}✓ Updated pyproject.toml${NC}"

# Update src/alur/__init__.py
sed -i.bak "s/^__version__ = .*/__version__ = \"${VERSION}\"/" src/alur/__init__.py
rm -f src/alur/__init__.py.bak
echo -e "${GREEN}✓ Updated src/alur/__init__.py${NC}"

# Update README.md current version
sed -i.bak "s/\*\*Current Version:\*\* [0-9.]*/**Current Version:** ${VERSION}/" README.md
rm -f README.md.bak
echo -e "${GREEN}✓ Updated README.md${NC}"

# Reminder to update CHANGELOG.md
echo ""
echo -e "${YELLOW}⚠️  REMINDER: Update CHANGELOG.md manually${NC}"
echo "   Add entry for [${VERSION}] - $(date +%Y-%m-%d)"
echo ""
read -p "Press Enter when CHANGELOG.md is updated..."

echo ""
echo -e "${YELLOW}Step 3/6: Committing version bump...${NC}"
git add pyproject.toml src/alur/__init__.py README.md CHANGELOG.md
git commit -m "chore: bump version to v${VERSION}"
echo -e "${GREEN}✓ Version bump committed${NC}"

echo ""
echo -e "${YELLOW}Step 4/6: Pushing to main...${NC}"
git push origin main
echo -e "${GREEN}✓ Pushed to main${NC}"

echo ""
echo -e "${YELLOW}Step 5/6: Creating git tag...${NC}"
git tag -a "${TAG}" -m "Release ${TAG}: ${DESCRIPTION}"
echo -e "${GREEN}✓ Tag ${TAG} created${NC}"

echo ""
echo -e "${YELLOW}Step 6/6: Pushing tag to GitHub...${NC}"
git push origin "${TAG}"
echo -e "${GREEN}✓ Tag pushed to GitHub${NC}"

echo ""
echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}Release ${TAG} initiated!${NC}"
echo -e "${GREEN}====================================${NC}"
echo ""
echo "Next steps:"
echo "1. Monitor GitHub Actions: https://github.com/ParmenidesSartre/Alur/actions"
echo "2. Verify PyPI: https://pypi.org/project/alur-framework/${VERSION}/"
echo "3. Create GitHub Release: https://github.com/ParmenidesSartre/Alur/releases/new?tag=${TAG}"
echo ""
echo "GitHub Actions will automatically build and publish to PyPI."
echo ""
