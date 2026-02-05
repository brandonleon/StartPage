run:
  uv run uvicorn main:app --reload

bump level:
  uv version --bump {{level}}

# Build and replace running Docker container
docker-replace:
  #!/usr/bin/env bash
  set -euo pipefail

  echo "🔨 Building new image..."
  docker build . -t startpage

  echo "🛑 Stopping and removing existing container..."
  docker stop startpage 2>/dev/null || true
  docker rm startpage 2>/dev/null || true

  echo "🚀 Starting new container..."
  docker run -d -p 8080:8080 --restart=always --name startpage -v ~/.config/startpage:/usr/startpage/data startpage

  echo "✅ Container replaced successfully!"
  docker ps --filter name=startpage

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
