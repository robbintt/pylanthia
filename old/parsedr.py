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


    game_state = dict()

    game_state['time'] = 0

    game_state['exits'] = ['n', 'e', 's', 'w', 'ne', 'se', 'nw', 'sw']

    # replay some lines from a raw log
    # if you don't have this, just make it here or in your preferred location
    # if you have no raw logs, run the client for a bit to build one
    with open('logs/tcp.txt') as f:
        raw_lines = f.readlines()

    # reimplemented from pylanthia.py
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

            # have to determine if broken or if multiline
            result = parse_broken_xml(line[1])
            for action, elem in result:
                print("{}: {}, tag: {}, attrib: {}".format(action, elem, elem.tag, elem.attrib))
                if elem.tag == 'prompt' and elem.attrib.get('time'):
                    print("TIME: ", elem.attrib.get('time'))
                if elem.tag == 'compass':
                    print('COMPASS DIR ELEMENTS: ', dir(elem), elem.iterchildren('d'))
                    for direction in elem.iterchildren('dir'):
                        print('exit value attrib:', direction.attrib['value'])
            input("> press enter to continue...") # just wait for the user to continue

        elif line[0] == 'text':
            final_lines.append(line[1])
            print(line[1])

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



