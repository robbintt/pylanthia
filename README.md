# Pylanthia

A terminal-based dragonrealms client in Python. Lich is used as a scripting backend.

## Setup

This needs improved to run multiple instances with different configs from the same install.

Also I want to get rid of the pipenv install every single startup...

- Clone this repo
- Go into vendor and run `./setup.sh`
- Fill in your `config.py`
- Run `docker-compose build` to create the docker container
- I think I need to do a first-time setup of dependency.lic and other lich scripts??

## Play Instructions

Once set up, simply `docker-compose run pylanthia` to start the service.

### Lich setup

See [[docs/lich.md]]

- Lich commands seem to be run by using an escape, e.g. `\;rocks`, `\;killall`.
- I don't remember this, so need to check game logs and pylanthia regex...

- There was some lich first time setup that might require automation each time the docker image is created. Hopefully idempotent.
