FROM ruby:latest as base

# secrets still come from config.py which is mounted
# FUTURE: secrets can come from .env when docker-compose entrypoint is hit...

# gtk2 no longer necessary in current lich? working fine without...
RUN gem install sqlite3

RUN apt-get update
RUN apt-get install -y python3-pip
RUN pip3 install pipenv

# this gets used to setup pipenv, then the volume shadows it
RUN mkdir /app
WORKDIR /app
COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock
# install into system? not sure if i want --system
# --deploy fails the install if lockfile is out of date
# https://pipenv-fork.readthedocs.io/en/latest/advanced.html#using-pipenv-for-deployments
#RUN pipenv install --system --dev
RUN pipenv sync

# not working... i put this inside of start.sh instead
#COPY deploy/openssl.cnf /etc/ssl/openssl.cnf
