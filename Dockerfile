# ruby:2.6.6 pinned for now, required by lich scripts in https://github.com/rpherbig/dr-scripts/
FROM ruby:2.6.6 as base

# secrets still come from config.py which is mounted
# FUTURE: secrets can come from .env when docker-compose entrypoint is hit...

# gtk2 no longer necessary in current lich? working fine without...
RUN gem install sqlite3

# lazy setup dependencies, this could be more explicit for pyenv/pipenv
RUN apt-get update

# this gets used to setup pipenv, then the volume shadows it
RUN mkdir /app
WORKDIR /app
COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock
COPY .python-version .python-version

# set up pyenv
ENV PYENV_ROOT /.pyenv
RUN curl https://pyenv.run | bash
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH
RUN pyenv install

# set up pipenv
RUN pyenv exec pip install pipenv
RUN pyenv exec pipenv sync
