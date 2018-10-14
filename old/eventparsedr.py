''' Parse the xml-like token stream coming from DR

User iterwalk to walk the stream

Might want to fix up certain tags before feeding them into this...

If everything is broken, we probably have to write our own walker after all

This is probably best called per xml token that is found


Which means we still need some sort of xml splitter, which is susecptible to breakage.
Any time we get a < we will basically risk triggering the xml splitter.
On failure the xml splitter should display text anyways
But malicious xml in uncontrolled input could cause UI issues


lxml has an Incremental Event Parser but I have major concerns about the XML stuff we have.

SIDENOTE:
    Optimistically: if we consider each line to be its own XML stream provided that
    the line starts with a '<', then we might be able to parse each line individually.

IMPORTANT:
    - I think I need all my windows to be set on... how do i do that: deaths, login, logout, etc.
    - Players will need to turn all these on to get all the streams
    - If one is off the stream should just be empty though, no big deal
'''
from lxml import etree
from io import BytesIO 
from collections import deque

def parse_broken_xml(broken_xml):
    ''' Chop up some broken xml and get any data out
    '''

    events = ('start', 'end')
    context = etree.iterparse(BytesIO(broken_xml.encode('utf-8')), events=events, recover=True)

    return context



if __name__ == '__main__':

    events = ('start', 'end')
    #parser = etree.XMLPullParser(events, recover=True)


    # replay some lines from a raw log
    # if you don't have this, just make it here or in your preferred location
    # if you have no raw logs, run the client for a bit to build one
    with open('../logs/tcp.txt') as f:
        raw_lines = f.readlines()

    def print_events(parser):
        for action, elem in parser.read_events():
            print("feed={}: {}, tag: {}".format(action, elem, elem.tag))
            print("attribute dict:", elem.attrib)
            print("tostring:", etree.tostring(elem))
            print("tostring:", elem.tail)

    # https://lxml.de/parsing.html#event-types (hmm)
    # https://lxml.de/parsing.html#incremental-event-parsing
    # what if i do each line as a feed, and if it doesn't end, then it chews some more...
    i = 1
    while i < len(raw_lines):
        line = raw_lines[i]
        if line[0] == '<':
            parser = etree.XMLPullParser(events, recover=True) # we don't want to raise errors
            print("raw=", line)
            parser.feed(line)
            print_events(parser)
            import time; time.sleep(1)
        else:
            # so far this is only <d> tags and <a> links in the game copy...
            # i think <d> tags are monster bold. we can manage them elsewhere
            if '<' in line:
                print("THE NEXT LINE HAS XML IN THE MIDDLE:")
            print("text line=", line)
        i += 1

    '''
    labelled_raw_lines = deque()
    for line in raw_lines:
        if line[0] == '<':
            labelled_raw_lines.append(('xml', line))
        else:
            labelled_raw_lines.append(('text', line))
            
    final_lines = deque()
    for line in labelled_raw_lines:
        if line[0] == 'xml':
            print("RAW: ", line[1])
            result = parse_broken_xml(line[1])
            for action, elem in result:
                print("{}: {}, tag: {}".format(action, elem, elem.tag))
            input("press enter to continue...") # just wait for the user to continue
        # always the case unless something breaks)
        elif line[0] == 'text':
            final_lines.append(line[1])
            print(line[1])
    '''

    '''
    xml = '<root><a><b /></a><c /></root>'
    broken_xml = '<root><a><b /></a><c />'
    print(broken_xml)

    result = parse_broken_xml(broken_xml)
    '''

    '''
    for action, elem in result:
        print("{}: {}, tag: {}".format(action, elem, elem.tag))


    print(context.root.tag)
    '''



