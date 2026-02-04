run:
  uv run uvicorn main:app --reload

bump level:
  uv version --bump {{level}}

# Release workflow: commit, tag, and push
release message:
  #!/usr/bin/env bash
  set -euo pipefail
  # Get version from pyproject.toml
  VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)

  echo "📦 Releasing version v$VERSION"
  echo "💬 Commit message: {{message}}"

  # Stage all changes
  git add .

  # Commit
  git commit -m "{{message}}"

  # Create annotated tag
  git tag -a "v$VERSION" -m "Release v$VERSION"

  # Push commits and tags
  git push --follow-tags

  echo "✅ Released v$VERSION successfully!"

# Bump version and release in one command
bump-release level message:
  just bump {{level}}
  just release "{{message}}"
