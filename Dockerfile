FROM ruby:latest 

# secrets still come from config.py which is mounted
# FUTURE: secrets can come from .env when docker-compose entrypoint is hit...

# gtk2 no longer necessary in current lich? working fine without...
RUN gem install sqlite3

RUN apt-get update
RUN apt-get install -y python3-pip
RUN pip3 install pipenv

# not working... i put this inside of start.sh instead
#COPY deploy/openssl.cnf /etc/ssl/openssl.cnf
