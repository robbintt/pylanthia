''' A terminal-based python client for dragonrealms

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
    5. need persistent data structure to store 'ignore filters' and 'color filters'
        - SQLite or flat config file
        - maybe a flat config file at first so it can be configured outside the game
        - ability to hot reload the flat config
        - how will a player use filters to create new streams?
            - this is a killer feature



TODO:
    - log per character name
    - make a 'last played' log that is easier to tail for debugging and building xml
    - separate xml parsing into its own data structure, consider sqlite if huge



'''
import socket
import threading
import queue

import time
import itertools
import re
import datetime
import logging
import os

from lxml import etree

import urwid
import urwid_readline

# this is not thread safe... need Queue.Queue
# Queue.Queue uses collections.deque and adds thread safety
from collections import deque
from itertools import islice
# lowercase in python3
import queue

from config import *
from eaccess import get_game_key

TCP_BUFFER_SLEEP = 0.01 # not sure if i want to sleep this or not
SCREEN_REFRESH_SPEED = 0.1 # how fast to redraw the screen from the buffer
BUF_PROCESS_SPEED = 0.01 # this is a timer for the buffer view creation thread
BUFSIZE = 16 # This seems to give a better response time than 128 bytes

# set up logging into one place for now
log_filename = "{}_log.{}.txt".format('dr', datetime.datetime.now().strftime('%Y-%m-%d.%H:%M:%S'))
log_directory = "logs"
log_location = os.path.join(log_directory, log_filename)
logging.basicConfig(filename=log_location, level=logging.INFO)

class GlobalGameState:
    '''
    '''
    def __init__(self):
        '''
        '''
        self.roundtime = 0
        self.time = 0



# dump tcp separately
tcplog_filename = "{}_tcplog.{}.txt".format('dr', datetime.datetime.now().strftime('%Y-%m-%d.%H:%M:%S'))
tcplog_directory = "tcplogs"
tcplog_location = os.path.join(log_directory, tcplog_directory, tcplog_filename)

# check this once here, needs to be elsewhere though
if not os.path.exists(tcplog_location):
    with open(tcplog_location, 'w') as f:
        f.write('')


def chop_xml_and_text_from_line(line):
    ''' Given a line chop it into xml and text sections

    Currently used in process_lines

    Note the xml is not real xml, for now we're parsing it manually.
    Might consider just reforming it into xml and using lxml to parse attr:value pairs and content

    return an ordered and parsed list of: [string value, xml or text?]
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

    #logging.info(op_line)

    return op_line


def process_lines(tcp_lines, player_lines):
    ''' process the deque of tcp lines back to front, works in a separate thread

    need thread safety on: tcp_line and player_line (both collections.deque type)
    player_line will also be written to a file and only 4000 lines will stay in the buffer
    tcp_line will also be written to as it is parsed from the tcp_buffer

    processing the xml-style tokens is weird
        ex. inventory streamWindow - primes inventory, but there are still more indicators...
            the final xml before the inv text is: <pushStream id='inv'/>Your worn items are:\r\n
            then after the inv text is: <popStream/>\r\n
    if i could process this multiline token, it would solve some of my issue
    a ton of tokens are duplicate and can just be dropped
    ''' 
    
    def tcp_buffering():
        ''' wait for another line, sleep is the same as the tcp buffer thread
        '''
        while tcp_lines.empty():
            time.sleep(BUF_PROCESS_SPEED)

    ''' 
    all this multiline processing seems to be causing some slowness
    it's probably because it's a cludgy trash way of doing things
    nonetheless, it might be nice to pass these partial strings to the renderer...
    but i really don't think it's necessary, i think this logic just needs smoothed out
    '''

    while True:

        # only process a line if one exists
        if not tcp_lines.empty():

            # if the line disappears this will block until another is ready
            # this is the only consumer of tcp_lines, so this is not noteworthy
            # but this is already written, so enjoy.
            line = tcp_lines.get()

            op_line = chop_xml_and_text_from_line(line)

            # process xml in place, sometimes process_game_xml will need to hold the line until
            # it gets enough lines for a particular multi-line XML element
            # so that will be some sort of object?
            # for now we are just processing single line XML with a function...
            if op_line and op_line[0][0] == 'xml':
                op_line = process_game_xml(op_line)

            rebuilt_line = b''.join(x[1] for x in op_line)
            player_lines.append(rebuilt_line)
        else:
            # if there are no lines, maybe give a spinning wheel or a timeout
            pass

        # this sleep throttles max line processing speed
        # it doesn't gate tcp_lines.get() because that function will wait on its own.
        time.sleep(BUF_PROCESS_SPEED)


def process_game_xml(op_line):
    ''' Get any game state out of the XML, return a replacement line

    I think I'll need an empty line filter after this, since game state will often
    return nothing except in a UI indicator. Don't go too far with this though since
    lines will also be filtered into streams for composition by users.

    This is a temporary function, it will probably end up being an object that has the
    ability to hold a line and request more lines. Some XML elements are always
    multiline and we want to be able to parse those as a single glob.

    The failure state (xml not processed) should leave the XML in the display, so the
    player can report the issue and work around it without missing an important detail.
    '''
   
    # use the same rebuilt_line code pattern from above
    # the current text/xml chopper actually chops xml by tag... which ruins it
    # commented rebuilt line for now bc we're individually pulling each op_line tag
    #rebuilt_line = b''.join(x[1] for x in op_line)
    # assign this for now so we don't have to rename the variable for testing

    logging.info("RAW XML:" + repr(op_line))
    
    modified_line = ''
    def parse_events(parser, root_element, still_parsing):
        ''' quick and dirty, show the time events
        '''
        
        for action, elem in parser.read_events():

            # store the root element so we can check when it closes
            if root_element is None:
                root_element = elem

            # end parsing when the root element closes
            if action == 'end' and elem is root_element:
                still_parsing = False

            # lets see some stuff temporarily
            if action == 'end':
                logging.info("Element processed (action = end):" + elem.tag)


            for e in elem.iter():
                ''' iterate over element and all descendants in tree

                i can do this without the tag and do actions based on the tag below to parse
                all xml... not sure if this is managing <standalone\> elements properly...
                '''

                if e.tag == 'popBold':
                    pass
                    # check the child element for elem prompt attrib time!
                    # or better, traverse the child elements
                    # or even better, stop parsing elements ending with a /> as having a closing tag...

                # i thought this descended into all elements of the tree and would find all of these
                if e.tag == 'prompt' and e.attrib.get('time'):

                    # this doesn't always log, and it never seems to show up in the processed text
                    # may just be where my processed text feed is coming from still of course
                    # i think the parser is missing the child elements though
                    # need to iterate descendants?? what clean way to do this...
                    modified_line = ('text', 'THE TIME IS:', e.attrib.get('time'))
                    logging.info(modified_line)
                    logging.info('** TIME ** ' + e.attrib.get('time'))
                    global_game_state.time = int(e.attrib.get('time'))

                # <roundTime value='1543879803'/>
                if e.tag == 'roundTime' and e.attrib.get('value'):
                    logging.info('** ROUNDTIME ** ' + e.attrib.get('value'))
                    global_game_state.roundtime = int(e.attrib.get('value'))
                    


        return root_element, still_parsing


    # may want to specify more events and use the event in the control flow...
    events = ('start', 'end',)

    # run each line as its own xml... but this is a disaster as some have closing tags!
    linenum = 0
    while linenum < len(op_line):


        line = op_line[linenum]
        # this should only log root elements
        logging.info('root element?? should be! :' + repr(line))
        # only feed the line if it starts with xml... is this universally true?
        if line[0] == 'xml' and line[1]:

            logging.info('now build a parser for xml line content only:' + repr(line[1]))

            parser = etree.XMLPullParser(events, recover=True) # we don't want to raise errors
            
            # basically if the root end event has not fired, keep collecting...
            # how do i trigger that...
            # need to decide whether to grab another line here
            # essentially determine if this has a closing tag

            # feed lines until the root element is closed
            root_element = None
            still_parsing = True
            while still_parsing and linenum < len(op_line):

                # note that we DO feed text lines threaded inside an xml root element
                nextline = op_line[linenum] # same as line, but used/incremented in this while loop
                parser.feed(nextline[1])

                # examine the parser and determine if we should feed more lines or close...
                root_element, still_parsing = parse_events(parser, root_element, still_parsing)
                
                # avoid double increment in parent while loop
                if still_parsing:
                    linenum += 1
            else:
                logging.info("The final parsed XML output:" + repr(parser))


            #parser.close() # i think i need to do this... read up

        linenum += 1

    #logging.info(b'xml parsed:' + rebuilt_line)
    #parser.feed(rebuilt_line)

    # temporary, replace xml and inject 1 line
    if modified_line:
        return(modified_line)

    return op_line



def get_tcp_lines():
    ''' receive text and xml into a buffer and split on newlines

    this function does lock tcp_lines
    do we need a timer to give it back to the GIL?

    this thing does not sleep, i don't think it needs to
    the socket waits around a lot
    '''
    tcp_buffer = bytes()
    while True:
        tcp_chunk = gamesock.recv(BUFSIZE)

        # this is kind of a lot of writes... should be fine though
        with open(tcplog_location, 'a') as f:
            f.write(tcp_chunk.decode('utf-8'))

        # the buffer could f.read the last 4000 characters or something.. what's faster?
        # right now the buffer grows without limit, which is not the best...
        tcp_buffer += tcp_chunk

        if b'\n' in tcp_buffer:
            tcp_buffer_by_lines = tcp_buffer.split(b'\r\n')
            # grab the last one back
            tcp_buffer = tcp_buffer_by_lines.pop()
            # store the rest on the queue
            for line in tcp_buffer_by_lines:
                tcp_lines.put(line)
                    
            #logging.info("tcp lines processed: {}".format(len(tcp_buffer)))
        else:
            #logging.info("tcp line has no newline: {}".format(tcp_buffer))
            time.sleep(TCP_BUFFER_SLEEP)
            pass


def urwid_main():
    ''' just the main process for urwid... needs renamed and fixed up
    '''

    #uc_u = '\u25B2'
    '''
    uc_u = '\u2191'
    uc_d = '\u2193'
    uc_l = '\u2190'
    uc_r = '\u2192'

    uc_ul = '\u2196'
    uc_ur = '\u2197'
    uc_dr = '\u2198'
    uc_dl = '\u2199'
    '''

    # will want to assign an order to directions, once settled on a display method
    arrows = {}
    arrows['n'] = 'n'
    arrows['e'] = 'e'
    arrows['s'] = 's'
    arrows['w'] = 'w'
    arrows['nw'] = 'nw'
    arrows['ne'] = 'ne'
    arrows['sw'] = 'sw'
    arrows['se'] = 'se'

    status_line_string = '[ RT:  {roundtime} ]' + '[ ' + ' '.join([v for k, v in arrows.items()]) + ' ]'

    # imagine a function that adds a space or the arrow depending on
    # whether the compass arrow last received game state
    # currently just used to display them all as a placeholder

    fixed_size_for_now = 30
    main_window = urwid.Text('') # initalize the window empty
    input_box = urwid_readline.ReadlineEdit('> ', '') # pretty sure urwid_readline package needs Python3

    status_line = urwid.Text(status_line_string)

    mainframe = urwid.Pile([
        ('weight', fixed_size_for_now, urwid.Filler(main_window, valign='bottom')),
        ('fixed', 1, urwid.Filler(status_line, 'bottom')),
        ('fixed', 1, urwid.Filler(input_box, 'bottom')),
    ], focus_item=2)

    # these were for the terminal
    def set_title(widget, title):
        mainframe.set_title(title)

    def quit(*args, **kwargs):
        raise urwid.ExitMainLoop()

    '''
    def handle_key(key):
        if key in ('q', 'Q'):
            quit()
    '''
    

    def unhandled_input(txt, key):
        ''' why is this called unhandled input if it is the input handler??
        '''
        if key in ("enter"):
            # this really should be in some 'handled_input' function or something
            submitted_command = bytes(txt.edit_text, "utf-8")
            logging.info(submitted_command)

            # maybe timestamped as its own output stream, so it can be turned off on certain windows
            # this should actually go in player lines, not muddy up the tcp input...
            tcp_lines.put(b'> ' + submitted_command)

            txt.set_edit_text('')
            txt.set_edit_pos(0)

            # not sure if sending this has a buffer? or is it lag in the receive side...
            gamesock.sendall(submitted_command + b'\n')
            if submitted_command in [b'exit', b'quit']:
                raise Exception("Client has exited, use exception to cleanup for now.")
            return

        if key in ("ctrl q", "ctrl Q"):
            #raise urwid.ExitMainLoop()
            quit()

        input_box.set_edit_text("unknown key: " + repr(key))
        input_box.set_edit_pos(len(txt.edit_text))

    '''
    # supposed to fix focus loss, i don't have that issue yet
    # and it may be solved where i set handle_mouse=False in MainLoop
    def mouse_event(self, size, event, button, col, row, focus):
        pass
    '''

    #urwid.connect_signal(term, 'title', set_title)
    #urwid.connect_signal(term, 'closed', quit)

    # reference: http://urwid.org/reference/main_loop.html
    loop = urwid.MainLoop(
        mainframe,
        handle_mouse=False,
        unhandled_input=lambda key: unhandled_input(input_box, key))

    def refresh_screen(loop, player_lines):
        #view_lines_buffer = list() # a buffer of lines sent to the terminal
        while True:
            # ideally we could just check if loop is running
            # is there a data flag on loop we can pause until is True (loop.run() started)

            # do this first so that the urwid MainLoop 'loop' exists! otherwise too fast
            # it would be better to kick this off inside loop.run I think
            time.sleep(SCREEN_REFRESH_SPEED)


            status_line_contents = dict()
            # calculate remaining roundtime
            current_roundtime = int(global_game_state.roundtime - global_game_state.time)
            if current_roundtime < 0:
                current_roundtime = 0
            status_line_contents['roundtime'] = current_roundtime

            # format the status line with the current content values
            status_line_output = status_line_string.format(**status_line_contents)
        
            # set thae status line
            mainframe.contents[1][0].original_widget.set_text(status_line_output)

            # slice a view buffer off of player_lines
            # if the view buffer is too long, urwid currently cuts off the bottom, which is terrible... how to fix?
            # can we tap into the current height of the flow widget and give that as the view buffer size?
            view_buffer_size = fixed_size_for_now
            if len(player_lines) < view_buffer_size:
                _min_slice = 0
            else:
                _min_slice = len(player_lines) - view_buffer_size 

            view_buffer = itertools.islice(player_lines, _min_slice, len(player_lines))

            # ideally a 4000 line buffer view of the current game would be updated elsewhere and just displayed here
            # right now it just passes the current lines
            main_view_text = b'\n'.join(view_buffer)

            # the contents object is a list of (widget, option) tuples
            # http://urwid.org/reference/widget.html#urwid.Pile
            mainframe.contents[0][0].original_widget.set_text(main_view_text)

            loop.draw_screen()


    # refresh the screen in its own thread.
    refresh = threading.Thread(target=refresh_screen, args=(loop, player_lines))
    refresh.daemon = True # kill the thread if the process dies
    refresh.start()

    loop.run()


def setup_game_connection(server_addr, server_port, key, frontend_settings):
    ''' initialize the connection and return the game socket
    '''

    gamesock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = (server_addr, int(server_port))
    gamesock.connect(server)

    time.sleep(1) # would be better to get an ACK of some sort before sending the token...
    gamesock.sendall(key)
    gamesock.sendall(b'\n')
    gamesock.sendall(frontend_settings)
    gamesock.sendall(b'\n')

    # needs a second to connect or else it hangs, then you need to send a newline or two...
    time.sleep(1)
    gamesock.sendall(b'\n')
    gamesock.sendall(b'\n')

    return gamesock


def gametime_incrementer(global_game_state):
    '''
    '''
    while True:
        time.sleep(1)

        # this is incremented since we only get gametime about every 5-20 seconds
        global_game_state.time += 1


if __name__ == '__main__':
    ''' Set up the connection and start the threads
    '''
    global_game_state = GlobalGameState()

    tcp_lines = queue.Queue() # split the tcp buffer on '\r\n'
    player_lines = deque() # process the xml into a player log, which can also be a player view
    
    GAME_KEY = get_game_key(eaccess_host, eaccess_port, username, password)

    # hopefully we can reuse this to reload the game if it breaks
    gamesock = setup_game_connection(server_addr, server_port, GAME_KEY, frontend_settings)

    process_lines_thread = threading.Thread(target=process_lines, args=(tcp_lines, player_lines))
    process_lines_thread.daemon = True # closes when main thread ends
    process_lines_thread.start()

    tcp_thread = threading.Thread(target=get_tcp_lines)
    tcp_thread.daemon = True #  closes when main thread ends
    tcp_thread.start()

    gametime_thread = threading.Thread(target=gametime_incrementer, args=(global_game_state,))
    gametime_thread.daemon = True #  closes when main thread ends
    gametime_thread.start()

    # start the UI and UI refresh thread
    # urwid must have its own time.sleep somewhere in its loop, since it doesn't dominate everything
    urwid_main()



