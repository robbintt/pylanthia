# Lich on Ubuntu 18.04 Headless

Currently it seems to be in wizard mode, but I want it in stormfront mode...

I know that lich runs in stormfront... so what's going on?

2019-09-08: did I ever figure this out?


# Ruby

[Install ruby on ubuntu 18 as root with rbenv](https://www.digitalocean.com/community/tutorials/how-to-install-ruby-on-rails-with-rbenv-on-ubuntu-18-04)

- used the most recent ruby version at the time: `2.6.0`.
- installed ruby as root with rbenv 
- ruby gems: sqlite3, gtk2

## Programming Ruby

- http://ruby-doc.com/docs/ProgrammingRuby/

# Apt

- the `gtk2` ruby gem seems to require `xorg` apt package
- ruby is not installed with apt, rbenv is used


# Running lich

Use manual game mode `-g` with `-s`  stormfront mode: `ruby lich/lich.rbw -s --game=DR -g dr.simutronics.net:4901`

- commented out the require line for gtk, around line 500+ in lich.rbw
- you cannot use `ruby lich.rbw -s --dragonrealms` to get the stormfront game string, it has a fixme flag and exits.

- ran `ruby lich/lich.rbw --dragonrealms` from root's home directory


## Setup

- You start in the general lich help channel, so do `;lnet tune DRPrime` twice to set it as your default...

- DR Lich First time setup: https://github.com/rpherbig/dr-scripts/wiki/First-Time-Setup
    - having issues with the first step - cannot find dependency.lic
