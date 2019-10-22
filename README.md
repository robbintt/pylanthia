# Pylanthia

A terminal-based dragonrealms client in Python. Lich is used as a scripting backend.

## Setup

This needs improved to run multiple instances with different configs from the same install.

Also I want to get rid of the pipenv install every single startup...

Problem: i think the default example config has the wrong host and port (sf port) and we need to use 4901 or whatever.

Problem: how do i get the map db in place without copying from old install?

Problem: Need to detect lich.rb or lich.rbw and use whichever is there.

Problem: How can I get the dependency ssl key to work? maybe file an issue on the scripts gh repo.

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


## Electron Client

Develop a draft of this after moving view buffers out of `urwid_ui`.

How does electron install work with a python backend and a docker compose `run` launching lich?

- I don't really think docker is necessary since I can just set the host to localhost and change the port in lich.
- How would I test this? Feed my pylanthia client a totally different port, then run lich subprocess with the incoming port as a cli option... but wait
  - The problem with lich is also the ruby setup, which the docker container handles.  So port management is not the only issue.

How can I handle python dependencies and ruby dependencies inside electron? I would want to rpc between dockerized processes within electron

Looks like it would be an electron + react + redux-electron + python subprocess + zerorpc.

Article: https://www.fyears.org/2017/02/electron-as-gui-of-python-apps-updated.html


## Some notes - move these


The client is implemented with socket and urwid.

Global variables may not yet be locked properly for threading,
especially when appending sent text to the stream.

There is some confusion about how much information newlines from the
server actually hold. The server does not seem to provide newlines between
consecutive xml tags so some data needs to be extracted from the stream

The stream can also be logged directly and replayed in order to test certain behavior.
This is probably the best place to start.

Processing steps before player sees lines:

    1. convert xml lines to events or 'window streams'
        - some streams:
            - room
            - backpack
            - inventory
            - health snapshot
            - roundtime
            - prompt/time
            - logins, logouts
            - deaths, raises, etc?
    3. 'ignore filter' the lines
        - a line is ignored if a substring is found in it
    4. 'color filter' the lines: 
        - substring search, potential for regex search
        - a line can be colored or just the substring/regex section of the string
        - need conversion of hex colors downscaled for terminal? mapping?
        - customize background and foreground color, per-character basis
    5. need persistent data structure to store 'ignore filters' and 'color filters'
        - SQLite or flat config file
        - maybe a flat config file at first so it can be configured outside the game
        - ability to hot reload the flat config
        - how will a player use filters to create new streams?
            - this is a killer feature


TCP Lines:
    - tcp lines are logged by appending to a file

Display lines:
    - player display lines should be displayed and logged after all processing
    - processing could all occur in the same thread?
    - Where are display lines consumed?
        - urwid loop thread
        - logging method?




TODO:
    - log per character name
    - make a 'last played' log that is easier to tail for debugging and building xml
    - separate xml parsing into its own data structure, consider sqlite if huge



