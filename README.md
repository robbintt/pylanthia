# Pylanthia

A terminal-based dragonrealms client in Python. Lich is used as a scripting backend.

## Setup

This needs improved to run multiple instances with different configs from the same install.

- Clone this repo
- Fill in your `config.py`
- Go into vendor and run `./setup.sh`
- run pylanthia: `./run <charname>`
  - Make sure docker is running before doing this
- follow these steps from [here](https://github.com/rpherbig/dr-scripts/wiki/First-Time-Setup)
  - copy dependency.lic over from dr-scripts
    - this is the equivalent of `\;repository download dependency.lic`
  - `\;dependency install
  - `\;e use_lich_fork`
  - sometimes you need to restart DR a few times at this step
    - It will say "invalid game client, choose one of the following..."
    - Just restart and debug a bit, all config seems right.
  - `\;repository download-mapdb` (works great)
  - \;autostart add --global roomnumbers
- Delete backups made by repository: ```rm lich/scripts/*.bak```
- Go into vendor/lich-scripts and run `./update.sh`

### Optional: dependency.lic developer setup

- Follow [these instructions](https://github.com/rpherbig/dr-scripts/wiki/Developer-Setup)

## Autostart

Add these scripts to your autostart and dependency.lic lich fork autostart.

- `;autostart add drinfomon roomnumbers percmoons`
- `;e autostart('rpa_sniper', false)`


## Play Instructions

Use `./run <charname>` to start the game.

charname does accept lowercased abbreviations, try it out.

### Lich setup

See [[docs/lich.md]]

- There was some lich first time setup that might require automation each time the docker image is created. Hopefully idempotent.


## Current Dev Direction

1. `pylanthia.py` needs broken into modules to be more digestible
2. Logging and Event Handling need improved, see [[docs/xml-handling.md]]


### Cached data

It would be nice to cache a lot of player data in regular format, so that connection can be brokered a bit differently in game, and state navigation can be somewhat done offline or without querying the game.  I guess the uses of cached state are to view it, or to queue up commands, or track events over time like training rate or bundle value, hunting times, etc... also possible to diff inventory etc.

The connection could be connected/disconnected from the game console or something. Not sure what value this adds, maybe character switching. Maybe multiple characters in an instance, i don't see the point of developing that yet.

### Buffer Bugs

-  sometimes the buffer skips ahead, i assume it's 1 line ahead of my position
  - this is best solved by changing the buffer manual mode detection method
    - when you move the buffer a flag should be flipped until you go back to the end, then it should follow the end again
- up/down is still unhandled, it needs handled by the urwid widget
- is it possible to tap into widget height to fill the height? this would be really nice for filling the screen without overflowing up (if that still happens)


### Buffering windows

The idea is to tab through windows and only see what you care about.

- basic modes:
  - filter out of a window
  - filter into a window
  - substitute part of a line
  - highlight a line

### Updating pip

- `pyenv install` needs `apt install zlib1g libsqlite3-dev libbz2-dev libffi-dev libreadline-dev libssl-dev` on ubuntu 18 ami
- `PIP_REQUIRE_VIRTUALENV=false pyenv install`
- `PIP_REQUIRE_VIRTUALENV=false pyenv exec pip install pipenv`
- now you can mess with your Pipfile and Pipfile.lock


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



