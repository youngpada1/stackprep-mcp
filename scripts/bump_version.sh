#!/usr/bin/env bash
# Usage: ./scripts/bump_version.sh patch|minor|major
# Bumps the version in pyproject.toml, commits, and tags.
set -euo pipefail

PART=${1:-patch}
CURRENT=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

case "$PART" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
  *) echo "Usage: $0 patch|minor|major"; exit 1 ;;
esac

NEW="$MAJOR.$MINOR.$PATCH"

sed -i '' "s/^version = \"$CURRENT\"/version = \"$NEW\"/" pyproject.toml

echo "Bumped $CURRENT → $NEW"

git add pyproject.toml
git commit -m "chore: bump version to $NEW"
git tag "v$NEW"

echo ""
echo "Run this to publish:"
echo "  git push && git push --tags"
