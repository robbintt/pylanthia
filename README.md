# Pylanthia

A terminal-based dragonrealms client in Python.


## Goal

Provide many of the useful features, including scripting, of dragonrealms clients, in a terminal.


## Current Plans

1. How do I change focus in urwid and scroll the history? 
  - Can I do it with a hotkey? Maybe pageup/pagedown?
1. Clean up exit so it looks right
  - What is the exception cleaning up for me? Do I need to exit the socket?
1. Get all threads handling exceptions into the logging log.
1. rewrite the xml to use .text and .tail for text
  - any line that starts with xml is xml, no more xml splitting
  - any line that starts with text is text
1. band-aid on 'say' and 'whisper' xml parsing (can't see who is talking)
1. Implement stream on death or whatever, depends on xml rewrite
1. add the text stream highlight/alter and the text stream ignores
  - and text stream triggers?
1. make it so a down arrow when at the end of the history gives a blank line


## Release Plan

1. How to announce releases? updates?
  - How to poll for feature requests?
  - 
1. Clear Community Expectations
  - Alpha, for programmers
  - have a draft of the electron client??
    - avoid getting scooped by another developer (unfortunate reality)
1. Install guide
  - detailed Lich Install
  - OS Support
    - Mac
    - Linux
    - Windows
1. Lich documentation links in README
1. Patreon Donations
  - A la carte - Any number of characters $3/month (per account)
  - Starving Artist - $5/month
  - Unlimited Accounts - $12/month
  - Support Open Source Clients - $25/month
  - I need this to exist - $50/month
  


## Finished

1. Scoll `up` and `down` command history would be nice
  - `left` could clear the line
  - `right` would clear the `rt_command_queue`


## Quickstart: Python 3 Environment with `virtualenv`

- install Python 3
- `virtualenv -p python3 env3`
- `. env3/bin/activate`
- `pip install -r requirements.txt`


## XML Extraction, Parsing, Management

Some data is stored within XML tags, some data is stored between XML tags, as expected.

Some updates that are pushed like room and inventory will need to grab text streams starting when a XML tag is parsed off and ending when its closing tag is parsed off.

Some updates like time, can start on a newline or can have the first tag on a previous line, I think.

So how do we snag text for particular xml tags?


## Socket and Stream Handling

The socket by default uses `\r\n` carriage returns, which look like `^M` and a newline in vim.

It might be a good idea to find a library for handling tcp instead of doing it myself.

This isn't my core problem though, so maybe do this later.  What I have works.

- [Exscript: for ssh and telnet connections](https://exscript.readthedocs.io/en/latest/index.html)
- [Pexpect: control a subprocess like telnet... not really for this](https://github.com/pexpect/pexpect)


## Other Dragonrealms Client Implementations

Here is some info about implementing a client: https://www.reddit.com/r/dragonrealms/comments/4e0e3h/host_name_and_port_number/

EAccess Protocol (get a token from user/pass): http://warlockclient.wikia.com/wiki/EAccess_Protocol

More eaccess (aka SGE Protocol): https://gswiki.play.net/SGE_protocol/saved_posts

stormfront protocol (warlock): http://warlockclient.wikia.com/wiki/StormFront_Protocol

A client that can interact and authenticate with an API service is sufficient. This can easily be done with react.
    - Client should be on a website
    - Client should poll state and refresh the UI
    - Client should be easy to type into
    - Client should have options to offer rich features

### Here is an elanthipedia entry on front ends

- https://elanthipedia.play.net/Front_end


## Simple POC

To connect to dragonrealms, 

- get a wizard version SAL file
    - You may need to spoof a windows internet explorer user agent in your browser
- get your game key from a `Charactername.sal` file.
- get the host and port from the `sal` file.
- `telnet host port`
    - or use `rlwrap telnet host port` for a readline wrapper (so you can enter commands without scroll)
- send the first line with only your `game key`
- press enter and then add a `\r` for newline (`\n` works in python, maybe just two newlines)
    - whitespace will probably work too?
- after the first newline, send the client string and a second newline
- after the fourth line, which is the second newline, the game will connect

