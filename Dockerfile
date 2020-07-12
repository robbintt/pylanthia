# ruby:2.6.6 pinned for now, required by lich scripts in https://github.com/rpherbig/dr-scripts/
FROM ruby:2.6.6 as base

# secrets still come from config.py which is mounted
# FUTURE: secrets can come from .env when docker-compose entrypoint is hit...

# gtk2 no longer necessary in current lich? working fine without...
RUN gem install sqlite3

# lazy setup dependencies, this could be more explicit for pyenv/pipenv
RUN apt-get update
RUN apt-get install -y python3-pip
RUN pip3 install pipenv

# this gets used to setup pipenv, then the volume shadows it
RUN mkdir /app
WORKDIR /app
COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

# set up pyenv
ENV PYENV_ROOT /.pyenv
RUN curl https://pyenv.run | bash
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
# annoyingly, i haven't yet mounted the version specified in .python-version
RUN pyenv install 3.8.0

# set up pipenv
RUN pyenv exec pipenv sync
