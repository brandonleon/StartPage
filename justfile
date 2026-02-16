help:
  @echo "install - install dependencies via uv."
  @echo "dockerbuild - build and run the container with persistent sqlite storage."
  @echo "run - run the application via uvicorn in a screen session."
  @echo "develop - run the application via uvicorn with autoreload."
  @echo "remove - remove the uv-managed virtual environment; links database remains intact."
  @echo "docker-replace - rebuild image and replace running startpage container."
  @echo "bump <level> - bump the project version."
  @echo "release <message> - commit, tag, and push the current version."
  @echo "bump-release <level> <message> - bump version and release."

install:
  uv sync

dockerbuild:
  mkdir -p ~/.config/startpage/
  docker build . -t startpage
  docker run -d -p 8080:8080 --restart=always --name startpage -v ~/.config/startpage:/usr/startpage/data startpage

run:
  screen -dmS startpage uv run uvicorn main:app

develop:
  uv run uvicorn main:app --reload

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
