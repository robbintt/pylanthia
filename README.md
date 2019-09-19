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
  - manually add `dependency.lic` as `repository.lic` ssl key won't work
  - follow: https://github.com/rpherbig/dr-scripts/wiki/First-Time-Setup
- at this point you have an upgraded lich fork `rbw` file
  - you must change the invocation to reflect the new filename `lich.rbw` in `start.sh`
- remember repository doesn't work so you have to download everything...
  - i then manually copied a map database into lich/data/DR/ from my old install
  - i then manually specified lich.rbw in the `start.sh` entrypoint command
- Next, I turned roomnumbers on: `\;roomnumbers`
  - was able to see roomnumbers from the map database
- next set up autostarts from the `dependency.lic` first-time-setup (linked above)
  - ;e autostart('roomnumbers')


## Play Instructions

Once set up, simply `docker-compose run pylanthia` to start the service.

### Lich setup

See [[docs/lich.md]]

- Lich commands seem to be run by using an escape, e.g. `\;rocks`, `\;killall`.
- I don't remember this, so need to check game logs and pylanthia regex...

- There was some lich first time setup that might require automation each time the docker image is created. Hopefully idempotent.


## Current Dev Direction

1. `pylanthia.py` needs broken into modules to be more digestible
2. Logging and Event Handling need improved, see [[docs/xml-handling.md]]
