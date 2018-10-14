''' A terminal-based python client for dragonrealms

The client is implemented with socket and urwid.

Global variables may not yet be locked properly for threading,
especially when appending sent text to the stream.

There is some confusion about how much information newlines from the
server actually hold. The server does not seem to provide newlines between
consecutive xml tags so some data needs to be extracted from the stream

The stream can also be logged directly and replayed in order to test certain behavior.
This is probably the best place to start.

'''
import socket
import threading

import time
import itertools
import re
import datetime
import logging
import os

import lxml.etree

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
        while not tcp_lines:
            time.sleep(BUF_PROCESS_SPEED)

    ''' 
    all this multiline processing seems to be causing some slowness
    it's probably because it's a cludgy trash way of doing things
    nonetheless, it might be nice to pass these partial strings to the renderer...
    but i really don't think it's necessary, i think this logic just needs smoothed out
    '''

    while True:
        # should this use tcp_buffering function?
        if tcp_lines:

            line = tcp_lines.popleft()

            op_line = chop_xml_and_text_from_line(line)

            # process xml in place before this, this step leaves any unprocessed xml

            rebuilt_line = b''.join(x[1] for x in op_line)
            player_lines.append(rebuilt_line)
        else:
            # if there are no lines, maybe give a spinning wheel or a timeout
            pass

        # not sure an ideal sleep for this thread, maybe event based...
        time.sleep(BUF_PROCESS_SPEED)


def filter_lines(view_lines):
    ''' retired function with some ideas and features needed in a user-accessible filter tool

    would be good to be able to add filters, view filters by index, and delete filters

    good use for file or sqlite database... file is nice as users can share, can call a reload function

    the functionality here can be moved, if some other filter_lines exists, the context will be different
    '''


    # this still doesn't work because we need to filter xml above the line level
    # do newlines from the server ever contain meaningful data or are they pointless?
    # is all the newline data given by a terminating xml-type tag?

    # filter lines that start with an exclude string - non-regex
    excludes = ['<prompt time="']
    for exclude in excludes:
        view_lines = [line for line in view_lines if line[0:len(exclude)] != exclude]

    # first lets just rip out the xml... later we will want to process it back into the stream
    # mostly we can use the xml just to update the state, if that's the case then if we miss
    # one then it's no proble, we just catch the next one... provided they are regular enough.
    # if they are not, or set state once, then we definitely want to catch every one
    xml_free_lines = list()
    for line in view_lines:

        # assuming lines only have xml if they start with xml? interesting idea, not sure if real
        i = 0 
        xml_free_line_segments = list()
        xml_line_segments = list()
        xml_free_line_part = b''
        xml_line_part = b''
        ordered_parsed_line = list() # give a tuple of string, type

        # ISSUE: i'm pretty sure this is dropping a letter off the first non-xml line segment (or more)
        # make a bunch of line segments
        # note that line is a bytes() type, indexing line[i] returns int
        # if we slice into it line[i:i+1] we get a bytes() type of length 1
        while i < len(line):

            if line[i:i+1] != b'<':
                xml_free_line_part += line[i:i+1]

            else:

                # increment until you get out of the xml tag or out of the line
                while i < len(line) and line[i:i+1] != b'>':
                    xml_line_part += line[i:i+1]
                    i += 1

                # toss the last b'>' on the end!
                xml_line_part += line[i:i+1]

                # store the xml part off
                xml_line_segments.append(xml_line_part)
                ordered_parsed_line.append(('xml', xml_line_part))
                xml_line_part = b'' # reset the xml part


            # store xml free part off
            if len(xml_free_line_part) > 1:
                xml_free_line_segments.append(xml_free_line_part)
                ordered_parsed_line.append(('text', xml_free_line_part))
                xml_free_line_part = b'' # reset the xml_free_line_part

            i += 1 # covers incrementing past the '>' and incrementing if not yet in a '<'


        # for now just join the xml free parts and only show those... we can process the xml elsewhere

        '''
        # https://lxml.de/tutorial.html
        # if the xml cannot be parsed, we just want to catch it and decide what to do
        try:
            xml = [lxml.etree.XML(xml_line) for xml_line in xml_line_segments]
            xml_tags = [x.tag for x in xml]
            # just testing lxml tag parsing
            if b'streamWindow' in xml_tags:
                xml_free_lines.append(b'streamWindow skipped...')

        except lxml.etree.XMLSyntaxError:
            xml = list()  # no tags
            # toss any failing XML onto the text stream for manual parsing?
            # we can follow this approach even if we replace or wrap lxml with a manual parser
            xml_free_lines.extend(xml_line_segments)
        '''
        # do stuff with the xml components of the line
        op_line = ordered_parsed_line

        if op_line:

            if op_line[0][0] == 'xml':
                if op_line[0][1].startswith(b'<prompt time="'):
                    op_line.pop(0)


        # strip the line back down to text
        clean_line = [x[1].replace(b'&gt;', b'>') for x in op_line if x[0] == 'text']
        xml_free_lines.append(b''.join(clean_line))

        # send a hunk of xml so we can see what happened
        xml_line = [x[1].replace(b'&gt;', b'>') for x in op_line if x[0] == 'xml']
        xml_free_lines.append(b''.join(xml_line))



                        
    # just point it here for now so we don't have to change the return
    view_lines = xml_free_lines



    '''
    EXCLUDES = [
        r'<prompt.*>',
        r'</prompt.*>',
    ]

    SUBS = [
        (r'<.*>', ''),
    ]

    # drop empty lines before the regex to save processing
    # what about lines with whitespace only...
    view_lines = [line for line in view_lines if line != b'' or line != b'&gt']

    for exclude in EXCLUDES:
        view_lines = [str(line) for line in view_lines if not re.search(exclude, str(line))]

    for expr, sub in SUBS:
        view_lines = [re.sub(expr, sub, str(line)) for line in view_lines]

    # drop empty lines after the regex so they aren't shown
    view_lines = [line for line in view_lines if line != b'' or line != b'&gt']
    '''

    return view_lines


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
            tcp_lines.extend(tcp_buffer.split(b'\r\n'))
            tcp_buffer = tcp_lines.pop() # leave the uncooked portion
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
    arrows = {}
    arrows['n'] = 'n'
    arrows['e'] = 'e'
    arrows['s'] = 's'
    arrows['w'] = 'w'
    arrows['nw'] = 'nw'
    arrows['ne'] = 'ne'
    arrows['sw'] = 'sw'
    arrows['se'] = 'se'

    # imagine a function that adds a space or the arrow depending on
    # whether the compass arrow last received game state
    # currently just used to display them all as a placeholder

    # wrap the top text widget with a flow widget like Filler: https://github.com/urwid/urwid/wiki/FAQ
    #main_window = urwid.Text('\r\n'.join(tcp_lines))
    fixed_size_for_now = 30
    main_window = urwid.Text('') # initalize the window empty
    input_box = urwid_readline.ReadlineEdit('> ', '') # pretty sure urwid_readline package needs Python3
    status_line = urwid.Text('[RT: 5]' + '[ ' + ' '.join([v for k, v in arrows.items()]) + ' ]')
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

            # this should probably get tacked on later than raw tcp lines, 
            # maybe timestamped as its own output stream, so it can be turned off on certain windows
            tcp_lines.append(b'> ' + submitted_command)

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


            # currently just smash up the tcp line history, but need to change that
            #view_lines_buffer.extend(tcp_lines)
            #tcp_lines.clear()

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


if __name__ == '__main__':
    ''' Set up the connection and start the threads
    '''

    tcp_lines = deque() # split the tcp buffer on '\r\n'
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

    # start the UI and UI refresh thread
    # urwid must have its own time.sleep somewhere in its loop, since it doesn't dominate everything
    urwid_main()



