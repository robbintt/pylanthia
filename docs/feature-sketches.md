
# Feature Sketches


## Finished

1. Scoll `up` and `down` command history would be nice
  - `left` could clear the line
  - `right` would clear the `rt_command_queue`

### Docker Ideas

Docker is pretty good for this, I think. The only reason lich needs some privileges is to
proxy the game connection port. This makes docker a pretty good choice, since you can run
both lich and pylanthia in the same container, and the host doesn't need hijacked.


1. Ideally set up a few docker entrypoints
  1. `setup`: maybe a config wizard, maybe just drop you in bash in pylanthia folder
  1. `pylanthia` entrypoint - login to dragonrealms via pylanthia with lich activated
    - config secrets: ideally use envvars, config, or manual entry outside of the docker container

### Current Plans

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
1. Fix exit to happen in urwid_main event_loop... not sure how
1. Fix detection that global_game_state.time is set so that it doesn't happen every time
  - right now the global game state time tries to check that the time has been set EVERY TIME
  - needs to just do that once and avoid checking for the entire thread existence
  - there's also a hacky like > 100000 value that shouldn't be necessary


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
  

