restart:
  docker restart startpage

install:
  uv sync

dockerbuild:
  mkdir -p ~/.config/startpage/
  docker build . -t startpage
  docker run -d -p 8080:8080 --restart=always --name startpage -v ~/.config/startpage:/usr/startpage/data startpage

run:
  startpage uv run uvicorn main:app

develop port='8000':
  uv run uvicorn main:app --port {{port}} --reload

remove:
  rm -rf .venv

bump level:
  uv version --bump {{level}}

docker-replace:
  #!/usr/bin/env bash
  set -euo pipefail
  git pull

  echo "Building new image..."
  docker build . -t startpage

  echo "Stopping and removing existing container..."
  docker stop startpage 2>/dev/null || true
  docker rm startpage 2>/dev/null || true

  echo "Starting new container..."
  docker run -d -p 8080:8080 --restart=always --name startpage -v ~/.config/startpage:/usr/startpage/data startpage

  echo "Container replaced successfully."
  docker ps --filter name=startpage

release message:
  #!/usr/bin/env bash
  set -euo pipefail
  VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)

  echo "Releasing version v$VERSION"
  echo "Commit message: {{message}}"

  git add .
  git commit -m "{{message}}"
  git tag -a "v$VERSION" -m "Release v$VERSION"
  git push --follow-tags

  echo "Released v$VERSION successfully."

bump-release level message:
  just bump {{level}}
  just release "{{message}}"

# Push the locally-built image to ghcr.io (stable releases only — skips pre-releases)
ghcr-push:
  #!/usr/bin/env bash
  set -euo pipefail
  VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
  if echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "Tagging and pushing ghcr.io/brandonleon/startpage:$VERSION ..."
    docker tag startpage ghcr.io/brandonleon/startpage:"$VERSION"
    docker tag startpage ghcr.io/brandonleon/startpage:latest
    docker push ghcr.io/brandonleon/startpage:"$VERSION"
    docker push ghcr.io/brandonleon/startpage:latest
    echo "Done."
  else
    echo "Version '$VERSION' is a pre-release — skipping ghcr push."
    exit 1
  fi

# Pull the latest published image from ghcr.io and run it
ghcr-run:
  #!/usr/bin/env bash
  set -euo pipefail
  mkdir -p ~/.config/startpage/
  docker pull ghcr.io/brandonleon/startpage:latest
  docker run -d -p 8080:8080 --restart=always --name startpage \
    -v ~/.config/startpage:/usr/startpage/data \
    ghcr.io/brandonleon/startpage:latest
  echo "StartPage running at http://localhost:8080"

# Pull and replace a running container with the latest image from ghcr.io
ghcr-replace:
  #!/usr/bin/env bash
  set -euo pipefail
  echo "Pulling latest image from ghcr.io ..."
  docker pull ghcr.io/brandonleon/startpage:latest

  echo "Stopping and removing existing container ..."
  docker stop startpage 2>/dev/null || true
  docker rm startpage 2>/dev/null || true

  echo "Starting new container ..."
  docker run -d -p 8080:8080 --restart=always --name startpage \
    -v ~/.config/startpage:/usr/startpage/data \
    ghcr.io/brandonleon/startpage:latest

  echo "Container replaced successfully."
  docker ps --filter name=startpage
