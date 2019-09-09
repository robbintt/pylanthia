
## XML Extraction, Parsing, Management

Some data is stored within XML tags, some data is stored between XML tags, as expected.

Some updates that are pushed like room and inventory will need to grab text streams starting when a XML tag is parsed off and ending when its closing tag is parsed off.

Some updates like time, can start on a newline or can have the first tag on a previous line, I think.

So how do we snag text for particular xml tags?


## Log & Event Management: Prerequisite for handling XML parsing

The logs must show what happened with timestamps. It should be possible to thread them together by timestamp to see multiple layers in the same view.

I need the following logs to manage XML parsing better:
1. raw tcp output
  - already exists, critical for diagnostic
1. timestamped raw tcp chunk logging
  - can be rebuilt back into a single tcp output file like exists today
  - can be threaded with other timestamped logs to analyze what happened
  - TODO: can be replayed back onto the game client using the base timestamp as an offset
    - this is easy tooling
2. xml root element logging
  - can determine what actions to take based on root element content
    1. keep gathering (rare)
    2. trigger events: probably can use some sort of format for this
      - text output event
      - ui update event
      - flexible event types...
      - Event tuple: (event_type_str::str, last_tcp_timestamp::timestamp, data_content::dict)
        - most categories of events are text output events
        - TODO very frequent to have events that give console info like health/mana/etc.  
        - Data content is probably just json object compatible KV pairs
        - This creates the best flexibility for remapping event tuples onto a new UI and text streams


## A collection of tactics for handling a busted XML stream

I can tune cases down pretty far, then print any XML that doesn't fit a precise case.

Write a data format that explicitly represents each class of case and order of parsing.

Also consider how the parse tree works.  We should be accumulating output text across the parse tree.

XML can have displayed text in a variety of places, and can have tags inside those texts.  The tags can need further parsing.

Am I making things too complex by being in the wrong stream format e.g. stormfront format instead of wizard?

- Case: xml needs fixed to be parsed
  - lang barge and crossings ferry both have malformed XML
- Case: xml tag does not have a close tag or a `\>` modifier
  - `<popStream>` is an example of this
- Case: xml object is sometimes multiline
- Case: xml object is single line and has tail text

