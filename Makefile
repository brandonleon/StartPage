#Makefile

help:
	@echo "install - install dependencies via poetry."
# 	@echo "dockerbuild - Build container and setup sqlite3 db."
# 	@echo "dockerrun - Run the docker container with the --restart=always flag."
	@echo "run - Run the application via uvicorn in a screen session, screen -r to attach and then Ctrl+c to exit."
	@echo "develop - Run the application via uvicorn with auto reload, in the foreground."
	@echo "remove - remove all assets and dependencies, this will leave the links database intact."

install:
	pipx install poetry; poetry install

dockerbuild:
	docker build . -t startpage
	mkdir -p ~/.config/startpage/
	docker run -d -p 8080:8080 --restart=always --name startpage -v ~/.config/startpage:/usr/startpage/data startpage

run:
	screen -dmS startpage poetry run uvicorn main:app

develop:
	poetry run uvicorn main\:app --reload

remove:
	rm -rf $(poetry env info -p)