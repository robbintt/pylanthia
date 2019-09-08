FROM ruby:latest 

# secrets still come from config.py which is mounted
# FUTURE: secrets can come from .env when docker-compose entrypoint is hit...

# TODO: run lich, then run pylanthia
RUN mkdir /usr/src/app
