StartPage is a SelfHosted dynamic collection of links. Intended purpose is to run this application locally and then use it as your browsers start-page.

The list is dynamically ordered based on frecency.

Frecency is a portmanteau of 'recent' and 'frequency'. It is a weighted rank that depends on how often and how recently something occurred. As far as I know, Mozilla came up with the term.

To the application, a link that has a low ranking but has been recently accessed will quickly have higher scoes than a link that is accessed frequently but not recently.
## Virtual environment Installation (if you want to modify code).
1. Ensure you have [uv](https://github.com/astral-sh/uv) installed.
   ``` shell
   pipx install uv
   ```
2. Clone this repository.
   ``` shell
   git clone ssh://git@gitlab.servicenow.net:29418/brandon.leon/startpage.git
   ```
3. Install dependencies.
   ``` shell
   uv sync
   ```
4. Start the server in ether gunicorn or the flask development environment.
   Start the flask development server
   ```shell
   uv run uvicorn main:app --reload
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
