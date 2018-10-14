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

import urwid
import urwid_readline

from collections import deque
from config import *

import datetime
import logging

import os


SCREEN_REFRESH_SPEED = 0.1 # how fast to redraw the screen from the buffer
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


'''
# lets just dump to a file not log for now
tcplog_handler = logging.FileHandler(file_name)


root_logger = logging.getLogger()
root_logger.addHandler(tcplog_handler)
'''


def filter_lines(view_lines):
    ''' this was temporary and needs rebuilt with some terminal editable filter

    would be good to be able to add filters, view filters by index, and delete filters

    good use for file or sqlite database... file is nice as users can share, can call a reload function
    '''


    # this still doesn't work because we need to filter xml above the line level
    # do newlines from the server ever contain meaningful data or are they pointless?
    # is all the newline data given by a terminating xml-type tag?

    # filter lines that start with an exclude string - non-regex
    excludes = ['<prompt time="']
    for exclude in excludes:
        view_lines = [line for line in view_lines if line[0:len(exclude)] != exclude]


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
    '''
    tcp_buffer = bytes()
    while True:
        tcp_chunk = sock.recv(BUFSIZE)

        # this is kind of a lot of writes...
        with open(tcplog_location, 'a') as f:
            f.write(tcp_chunk.decode('utf-8'))

        # the buffer could f.read the last 4000 characters or something.. what's faster?
        # right now the buffer grows without limit, which is not the best...
        tcp_buffer += tcp_chunk

        if b'\n' in tcp_buffer:
            new_tcp_lines = True # maybe trigger the refresh here...
            tcp_lines.extend(tcp_buffer.split(b'\r\n'))
            tcp_buffer = tcp_lines.pop() # leave the last line, it's normally not cooked
            logging.info("tcp lines processed: {}".format(len(tcp_buffer)))
        else:
            new_tcp_lines = False
            logging.info("tcp line has no newline: {}".format(tcp_buffer))


def urwid_main():
    ''' just the main process for urwid... needs renamed and fixed up
    '''

    # wrap the top text widget with a flow widget like Filler: https://github.com/urwid/urwid/wiki/FAQ
    main_window = urwid.Text('\r\n'.join(tcp_lines))
    input_box = urwid_readline.ReadlineEdit('> ', '') # pretty sure this needs Python3
    mainframe = urwid.Pile([
        ('weight', 70, urwid.Filler(main_window, valign='bottom')),
        ('fixed', 1, urwid.Filler(input_box, 'bottom')),
    ], focus_item=1)

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
            tcp_lines.append(b'> ' + submitted_command)

            txt.set_edit_text('')
            txt.set_edit_pos(0)

            # not sure if sending this has a buffer? or is it lag in the receive side...
            sock.sendall(submitted_command + b'\n')
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

    def refresh_screen(loop, user_data=None):
        view_lines_buffer = list() # a buffer of lines sent to the terminal
        while True:
            # ideally we could just check if loop is running
            # is there a data flag on loop we can pause until is True (loop.run() started)

            # do this first so that loop exists! otherwise too fast
            time.sleep(SCREEN_REFRESH_SPEED)

            # the contents object is a list of (widget, option) tuples
            # http://urwid.org/reference/widget.html#urwid.Pile

            # currently just smash up the tcp line history, but need to change that
            view_lines_buffer.extend(tcp_lines)
            tcp_lines.clear()
            mainframe.contents[0][0].original_widget.set_text(
                    b'\n'.join(filter_lines(view_lines_buffer[-50:])))

            loop.draw_screen()


    # refresh the screen in its own thread.
    refresh = threading.Thread(target=refresh_screen, args=(loop,))
    refresh.daemon = True # kill the thread if the process dies
    refresh.start()

    loop.run()


if __name__ == '__main__':
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = (server_addr, int(server_port))
    sock.connect(server)

    time.sleep(1) # would be better to get an ACK of some sort before sending the token...
    sock.sendall(server_login_token)
    sock.sendall(b'\n')
    sock.sendall(frontend_setting)
    sock.sendall(b'\n')

    tcp_lines = deque() # would it be better to remove the newlines? ugh
    new_tcp_lines = True

    # needs a second to connect or else it hangs, then you need to send a newline or two...
    time.sleep(1)
    sock.sendall(b'\n')
    sock.sendall(b'\n')

    tcp_thread = threading.Thread(target=get_tcp_lines)
    tcp_thread.daemon = True # close with main thread
    tcp_thread.start()

    urwid_main()



