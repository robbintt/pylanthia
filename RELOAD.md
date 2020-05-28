# Reloading Features

Minimally I would like to reload my xml maps quickly.
Maybe these are all pulled in as a json configuration.
Then I can pull them in when the file is changed and the xml parsing just changes...
I think this could work.
- How does this work with using an object to build reprs from xml chunks?
- The XML object level is probably the object level for our message writing
  - Object relationship might matter, not sure how to write these structures...
  - For example, if this xml object is nested inside that object...
    - Well that actually just means the parent object is in our object map
      - The child object can be an xml object too in that tree...
    - We basically want to use our xml objects inside an extended python object 
    - The python object that is the xml object extension builds reprs and fires events



I want to reload application features from within the application for more rapid dev.

Some of this is unrealistic? Not sure.

What I'm really after is not losing my connection in feature reloads.

Do I need another application that handles the connection and proxies the port?
Can lich keep my port open?  I could keep the docker instance and treat pylanthia as a frontend for lich... lich isn't great to work in right now, is someone developing actively? I get changes...

