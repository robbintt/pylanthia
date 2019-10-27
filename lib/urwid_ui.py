'''
'''
import time
import threading
import queue
import itertools
import re
import textwrap

import urwid
import urwid_readline

from vendor.scroll.scroll import ScrollBar, Scrollable

import logging
logging.getLogger(__name__)

SCREEN_REFRESH_SPEED = 0.1 # how fast to redraw the screen from the buffer

def construct_view_buffer(text_lines, player_lines, highlight_list, excludes_list, view_buffer_size=30):
    '''
    # grab at most view_buffer_size lines per refresh
    # it makes sense for the view contents constructor to be elsewhere anyways
    '''
    i = 0
    while i < 4000:
        # careful this is blocking, if blocked we would want to just return what we have...
        # and even return some stuff from the last buffer attempt too!
        # hmm requires a little thinking!
        # for now we could make it a list and grow it forever...
        # then we can slice the last bit for the view again
        try:
            new_line = text_lines.get_nowait()
            # temporarily rebuild player_lines for viewing
        except queue.Empty:
            # return the player_lines when empty or 'full'/done
            break

        # munge new_line and convert bytes->utf-8
        new_line_str = b''.join([content for _, content in new_line]).decode('utf-8')+'\n'

        _skip_excluded_line = False
        for exclude_substr in excludes_list:
            if exclude_substr in new_line_str:
                _skip_excluded_line = True  # set flag to continue parent
                break
        if _skip_excluded_line == True:
            continue

        for highlight in highlight_list:
            if highlight in new_line_str:
                new_line_str = ('highlight', new_line_str)
                break # i guess just 1 highlight per string for now
                # write a recursive function? what about substrings?
                # there needs to be a color mask or something on the string index
                # (white, 5, 7), (red, 6, 7) - apply in order so last gets precedence, use python slice positional

        player_lines.append(new_line_str)
        i += 1

    # slice a view buffer off of player_lines
    if len(player_lines) < view_buffer_size:
        _min_slice = 0
    else:
        _min_slice = len(player_lines) - view_buffer_size

    # technique for slicing with a deque
    view_buffer = itertools.islice(player_lines, _min_slice, len(player_lines))
    #view_buffer = player_lines[_min_slice:]

    # just coerce to get out of this stupid isliced deque i don't need
    view_buffer_list = list()
    for line in view_buffer:
        view_buffer_list.append(line)

    if not view_buffer_list:
        view_buffer_list.append('')
    return view_buffer_list


def urwid_main(global_game_state, player_lines, text_lines, highlight_list, excludes_list, quit_event):
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

    color_palette = [
        ('banner', '', '', '', '#fff', 'g35'),
        ('statusbar', 'white', 'black'),
        ('highlight', 'white', '', '', 'g0', 'g35'),
        ('white', 'white', '', '', 'g0', 'g35'),
        ('inside', '', '', '', 'g0', 'g35'),
        ('outside', '', '', '', 'g0', 'g35'),
        ('bg', '', '', '', 'g35', '#fff'),]

    # note that these are ordered in Python 3.6+, this assumes you are running 3.6+ !!!
    arrows = {}
    arrows['n'] = 'n'
    arrows['e'] = 'e'
    arrows['s'] = 's'
    arrows['w'] = 'w'
    arrows['nw'] = 'nw'
    arrows['ne'] = 'ne'
    arrows['sw'] = 'sw'
    arrows['se'] = 'se'

    exit_string = ' '
    for k, v in arrows.items():
        if global_game_state.exits.get(k):
            exit_string += v
        else:
            exit_string += ' ' * len(v)  # preserve spacing from glyph
        exit_string += ' '  # separator whitespace

    # consider padding roundtime with 3 spaces
    status_line_string = '[ RT:  {roundtime}{roundtime_stable} ]' + '[{exit_string}]'
    #status_line_string = '[ RT:  {roundtime} ]' + '[ ' + ' '.join([v for k, v in arrows.items()]) + ' ]'

    # imagine a function that adds a space or the arrow depending on
    # whether the compass arrow last received game state
    # currently just used to display them all as a placeholder

    fixed_size_for_now = 4000
    main_window_buffer_size = 40
    main_window = ScrollBar(Scrollable(urwid.Text(''))) # initalize the window empty
    input_box = urwid_readline.ReadlineEdit('> ', '') # pretty sure urwid_readline package needs Python3

    status_line = urwid.Text(status_line_string)

    mainframe = urwid.Pile([
        ('weight', fixed_size_for_now, urwid.Filler(main_window, height=main_window_buffer_size, valign='bottom')),
        ('fixed', 1, urwid.Filler(status_line, 'bottom')),
        ('fixed', 1, urwid.Filler(input_box, 'bottom')),
    ], focus_item=2)

    # these were for the terminal
    def set_title(widget, title):
        mainframe.set_title(title)
    def quit(*args, **kwargs):
        raise urwid.ExitMainLoop()




    def unhandled_input(txt, key):
        ''' 
        much of this input should be handled in the pile or widgets inside the pile
        
        q: why is this called unhandled input if it is the input handler??
        a: ... urwid thing, this can probably be changed to whatever is appropriate, just use care

        '''

        if key in ("tab"):
            # rudimentary focus bouncer for now
            # ideally focus bounce will toggle buffers in the future
            if mainframe.focus_position == 2:
                mainframe.focus_position = 0
            else:
                mainframe.focus_position = 2
            return

        if key in ("enter"):

            global_game_state.history_scroll_mode = False  # toggle history scroll mode off

            if len(txt.edit_text) == 0:
                ''' ignore an empty command
                '''
                return
            
            submitted_command = txt.edit_text

            # allow multiple commands per line
            # this doesn't work for command history
            # maybe there should be an input history
            global_game_state.input_history.append(submitted_command)
            # replace newlines with semicolons so we can process them homogeneously
            # may need to work with urwid-rlwrap for custom multiline paste features
            # otherwise the major use case for this string replacement is not covered
            submitted_command = submitted_command.replace('\r', ';').replace('\n', ';')
            #logging.info('submitted line:' + submitted_command)

            # use a regex split here so that backslash can escape & 0send semicolon through the prompt
            re_semi_splitter = r'(?<!\\);'
            # replace all backslashes and strip all whitespace from the processed result
            submitted_commands = [c.replace('\\', '').strip() for c in \
                    re.split(re_semi_splitter, submitted_command)]
            #submitted_commands = submitted_command.split(';')

            for _s_c in submitted_commands:
                if len(_s_c) > 0:
                    _s_c = bytes(_s_c, "utf-8")
                    global_game_state.command_queue.put(_s_c)

            txt.set_edit_text('')
            txt.set_edit_pos(0)

            return

        if key in ("up", "down"):

            # deal with the 0 history case here
            if len(global_game_state.input_history) == 0:
                return

            # enter history scroll mode until the user presses enter
            if global_game_state.history_scroll_mode == False:
                global_game_state.history_scroll_mode = True
                global_game_state.input_history_counter = len(global_game_state.input_history) - 1

            # don't do this if you just set it to true! (elif)
            elif global_game_state.history_scroll_mode == True:

                if key in ("up"):
                    if global_game_state.input_history_counter > 0:
                        global_game_state.input_history_counter -= 1

                if key in ("down"):
                    if global_game_state.input_history_counter < len(global_game_state.input_history) - 1:
                        global_game_state.input_history_counter += 1

            input_box.set_edit_text(global_game_state.input_history[global_game_state.input_history_counter])
            input_box.set_edit_pos(len(txt.edit_text))
            return

        if key in ("left"):
            input_box.set_edit_text('')
            input_box.set_edit_pos(len(txt.edit_text))
            return

        if key in ("right"):
            ''' 
            interestingly, because of urwid-readline, i can use right and left arrows
            but only when there is already text on the line, and not on the far edges
            so on the far left, a left key will trigger this
            on the far right, a right key will trigger unknown key: right
            '''
            # need the mutex because this uses a function of the underlying deque
            # see: https://stackoverflow.com/a/6518011
            with global_game_state.rt_command_queue.mutex:
                global_game_state.rt_command_queue.queue.clear()
            return

        # not working
        if key in ("ctrl q", "ctrl Q"):
            #raise urwid.ExitMainLoop()
            quit()

        input_box.set_edit_text("unknown key: " + repr(key))
        input_box.set_edit_pos(len(txt.edit_text))
        return

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
        color_palette,
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

            # this really should be in the main thread...
            # urwid has event_loop that can probably handle this
            if quit_event.is_set():
                raise Exception('Client has exited, use exception to cleanup for now.')

            status_line_contents = dict()
            # calculate remaining roundtime
            current_roundtime = int(global_game_state.roundtime - global_game_state.time)
            if current_roundtime < 0:
                current_roundtime = 0
            if current_roundtime < 10:
                # pad < 10
                status_line_contents['roundtime'] = ' ' + str(current_roundtime)
            else:
                # don't pad > 10, note, for roundtimes 100+ there will be a shift in the UI. #wontfix
                status_line_contents['roundtime'] = '' + str(current_roundtime)

            exit_string = ''
            for k, v in arrows.items():
                if global_game_state.exits.get(k):
                    exit_string += v
                else:
                    exit_string += ' ' * len(v)  # preserve spacing from glyph
                exit_string += ' '  # separator whitespace

            status_line_contents['exit_string'] = exit_string

            # show the roundtime stable indicator if both time and roundtime are reported
            # this will be false only when the displayed roundtime is based on projected time
            # (global_game_state.time is projected time)
            if global_game_state.reported_time >= global_game_state.roundtime:
                status_line_contents['roundtime_stable'] = '.'
            else:
                status_line_contents['roundtime_stable'] = ' '

            # format the status line with the current content values
            status_line_output = status_line_string.format(**status_line_contents)

            # set thae status line
            mainframe.contents[1][0].original_widget.set_text(('statusbar', status_line_output))



            # ideally a 4000 line buffer view of the current game would be updated elsewhere and just displayed here
            # scrollable would also be really nice
            # right now it just passes the current lines
            #main_view_text = '\n'.join(construct_view_buffer(text_lines, player_lines, fixed_size_for_now))
            main_view_text = construct_view_buffer(text_lines, player_lines, highlight_list, excludes_list, fixed_size_for_now)

            # the contents object is a list of (widget, option) tuples
            # http://urwid.org/reference/widget.html#urwid.Pile
            mainframe.contents[0][0].original_widget._original_widget._original_widget.set_text(main_view_text)

            # update scroll position to bottom unless the person moved it
            # this should really just record if the user has modified the
            # scrollbar height and wait until they return it to max
            # hacky, jump once you get past the position you dropped off at
            scrollable_textbox = mainframe.contents[0][0].original_widget._original_widget
            _scrollpos = scrollable_textbox.get_scrollpos()
            if _scrollpos >=  global_game_state.urwid_scrollbar_last:
                scrollable_textbox.set_scrollpos(-1)
                # record the last possible position
                global_game_state.urwid_scrollbar_last = _scrollpos
            '''
            if mainframe.contents[0][0].original_widget._original_widget.get_scrollpos() != :
                mainframe.contents[0][0].original_widget._original_widget.set_scrollpos(-1)
            '''

            loop.draw_screen()


    # refresh the screen in its own thread.
    refresh = threading.Thread(target=refresh_screen, args=(loop, player_lines))
    refresh.daemon = True # kill the thread if the process dies
    refresh.start()

    loop.run()
