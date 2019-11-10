'''
'''
import time
from lib import xml_parser
import re
import logging

logging.getLogger(__name__)


def line_config_processor(filename):
    ''' Process a file into lines for ignores, highlights, etc.
    '''
    user_configured_lines = list()
    with open(filename) as f:
        for line in f:
            line = line.strip()
            if line and line[0] != '#' and not re.match(r'^\s+$', line):
                user_configured_lines.append(line)
    return user_configured_lines


def chop_xml_and_text_from_line(line):
    ''' Given a line chop it into xml and text sections

    A rudimentary xml tag parser for identifying where XML might start.

    The parser expects to return the raw XML if parse fails.

    There are situation where this process is too rudimentary.

    e.g. a player can use < in their free text 'chat' which could impact talk, whisper, etc.

    returns a list of tuples in the format: [(type_string, content_string), ...]
    '''

    # this function is no longer useful with lxml attached
    # see about getting rid of it?
    # here's a totally retooled version that should be a drop-in
    # it just preserves the interface and annotation data

    # always return bytes
    if not line:
        return [['text', b'']]
    # annotate and return a list of pairs
    # this needs to test for int, since indexing into a bytes gives an int
    if line[0] == b'<'[0]:
        return [['xml', line]]
    else:
        return [['text', line]]

    '''
    # make a bunch of line segments
    # note that line is a bytes() type, indexing line[i] returns int
    # if we slice into it line[i:i+1] we get a bytes() type of length 1
    xml_free_line_part = b''
    xml_line_part = b''
    op_line = list() # give an ordered and parsed list of: [string value, xml or text?]
    i = 0 
    while i < len(line):

        if line[i:i+1] != b'<':
            xml_free_line_part += line[i:i+1]

        # found some xml
        else:

            # store the text segment
            if xml_free_line_part:
                op_line.append(['text', xml_free_line_part]) # modify these in place later, sometimes
                #logging.info(b'text parsed: ' + xml_free_line_part)
                xml_free_line_part = b'' # reset the xml_free_line_part

            # increment until you get out of the xml tag or out of the line
            while i < len(line) and line[i:i+1] != b'>':
                xml_line_part += line[i:i+1]
                i += 1

            # toss the last b'>' on the end!
            xml_line_part += line[i:i+1]

            # store the xml part off
            op_line.append(['xml', xml_line_part]) # modify these in place later, sometimes
            #logging.info(b'xml parsed: ' + xml_line_part)
            xml_line_part = b'' # reset the xml part

        i += 1 # covers incrementing past the '>' and incrementing if not yet in a '<'


    # store any final text segment
    if xml_free_line_part:
        op_line.append(['text', xml_free_line_part]) # modify these in place later, sometimes
        #logging.info(b'text parsed: ' + xml_free_line_part)
        xml_free_line_part = b'' # reset the xml_free_line_part

    return op_line
    '''


def preprocess_tcp_lines(game_state, tcp_lines, preprocessed_lines):
    ''' Process the TCP lines into labelled lines for the XML parser
    '''
    while True:
        # block thread on tcp_lines.get()
        tcpline = tcp_lines.get()
        game_state.urwid_views['urwid_tcp_view'].append(tcpline.decode('utf-8'))
        preprocessed_lines.put(chop_xml_and_text_from_line(tcpline))


def process_lines(preprocessed_lines, text_lines, chat_lines, game_state):
    ''' process tcp lines back to front, works in a separate thread

    This function takes raw TCP lines and delivers annotated XML elements and text segments

    What if we use a preprocessor on the queue to create chop_xml_and_text_from_line's results
    THEN we have an XML puller thread that pulls those and processes them into XML events and another Queue
    THEN the `another queue` goes into the text filters and is displayed

    1. XML puller needs to be able to pull both XML and text lines (for multiline html text body)


    The DR output has some XML and some text.
    Sometimes a element stands alone, multiple elements per line. 
    Sometimes a element feeds into the next line.
    Sometimes XML output is multiline.
    Sometimes multiple XML structures are added on the same line.


    Goal:
    We need to be able to split a single line of multiple XML documents up.
    We also need to detect when multiple lines are one XML document.

    processing the xml-style tokens is weird
        ex. inventory streamWindow - primes inventory, but there are still more indicators...
            the final xml before the inv text is: <pushStream id='inv'/>Your worn items are:\r\n
            then after the inv text is: <popStream/>\r\n
    if i could process this multiline token, it would solve some of my issue
    a ton of tokens are duplicate and can just be dropped
    ''' 
    
    while True:
        # block thread on preprocessed_lines.get() calls (in the method)
        xml_parser.process_game_xml(preprocessed_lines, text_lines, chat_lines, game_state)
