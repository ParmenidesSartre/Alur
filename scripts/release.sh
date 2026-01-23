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
echo -e "${YELLOW}Step 1/5: Checking git status...${NC}"
if [[ -n $(git status -s) ]]; then
    echo -e "${RED}Error: Working directory has uncommitted changes${NC}"
    git status -s
    exit 1
fi
echo -e "${GREEN}✓ Working directory clean${NC}"

echo ""
echo -e "${YELLOW}Step 2/5: Bumping version numbers...${NC}"
python3 scripts/bump_version.py ${VERSION}
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Version bump failed${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 3/5: Committing version bump...${NC}"
git add .
git commit -m "chore: bump version to v${VERSION}"
echo -e "${GREEN}✓ Version bump committed${NC}"

echo ""
echo -e "${YELLOW}Step 4/5: Pushing to main...${NC}"
git push origin main
echo -e "${GREEN}✓ Pushed to main${NC}"

echo ""
echo -e "${YELLOW}Step 5/5: Creating and pushing tag...${NC}"
git tag -a "${TAG}" -m "Release ${TAG}: ${DESCRIPTION}"
git push origin "${TAG}"
echo -e "${GREEN}✓ Tag ${TAG} pushed to GitHub${NC}"

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
