StartPage is a SelfHosted dynamic collection of links. Intended purpose is to run this application locally and then use it as your browsers start-page.

The list is dynamically ordered based on usage.

## Virtual environment Installation (if you want to modify code).
1. Ensure you have poetry installed.
   ``` shell
   pipx install poetry
   ```
2. Clone this repository.
   ``` shell
   git clone ssh://git@gitlab.servicenow.net:29418/brandon.leon/startpage.git
   ```
3. Install dependencies.
   ``` shell
   poetry install
   ```
4. Start the server in ether gunicorn or the flask development environment.
   Start the flask development server
   ```shell
   poetry run uvicorn main:app --reload
   ```


## Docker Installation (if you simply want to run the application).
1. Clone this repository.
   ``` shell
   git clone https://gitlab.servicenow.net/brandon.leon/startpage.git
   ```
2. From the directory you just cloned, build the Docker image.
   ``` shell
   cd startpage; docker build . -t startpage
   ```
3. Create a data directory and run the docker container.
   ``` shell
   mkdir data;docker run -d -p 8080:8080 --restart=always --name startpage -v $(pwd)/data:/usr/src/app/data startpage
   ```