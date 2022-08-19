"""
"""
from lxml import etree
import re
import logging

logging.getLogger(__name__)


def parse_events(parser, root_element, still_parsing, text_lines, game_state):
    """ When an element ends, determine what to do

    these functions govern what is put in the text_lines Queue
    e.g. text_lines.put(whatever)

    A lot of data is given to the user by XML - store it in game state object
        - quick health
        - roundtime
        - inventory? some...
        - room contents
        - assess


    scenarios:
    1. For certain xml root tags, we want to grab multiline
        - which elements? we need a catalog
    2. For others, we just want part of the line
        - this is the default, just stop when you have the tag


    """

    def textbox_wrapper(unwrapped_string):
        ''' Helper to wrap an unwrapped string into a tuple with its type for urwid, and convert to bytes

        :type unwrapped_string: bytes

        Note: that this trailing comma is as-intended, a tuple of a tuple: ('text', bytes(unwrapped_string)),
        '''
        return ("text", unwrapped_string),


    for action, elem in parser.read_events():

        # store the root element so we can check when it closes
        if root_element is None:
            root_element = elem

        # fix this up
        if elem != root_element:
            continue

        # end parsing when the root element closes
        # what about if there's a tail?
        if action == "end" and elem is root_element:

            # i could check for a text tail here??
            still_parsing = False

        # lets see some stuff temporarily
        if action == "end":
            # logging.info("Element processed (action = end):" + elem.tag)
            pass

        e = elem
        # i think i just want to hit the element now, i will iter inside the function if necessary
        #        for e in elem.iter():
        #            ''' iterate over element and all descendants in tree
        #
        #            i can do this without the tag and do actions based on the tag below to parse
        #            all xml... not sure if this is managing <standalone\> elements properly...
        #
        #            use a dict of functions or something here
        #                - do i need to check tag name and attrib dict?
        #
        #            # in this case the functions still need to handle the attrib dict
        #            xml_actions = { 'popBold' : function1,
        #                            'prompt'  : function2 }
        #
        #
        #            '''

        def compass(elem):
            """ get all the dirs inside this

            <compass><dir value="n"/><dir value="e"/><dir value="se"/></compass>

            seems like the xml parser is processing the children seperately too
            """
            game_state.reset_exits()
            for direction in elem.iterchildren("dir"):
                if direction.attrib.get("value"):
                    if direction.attrib.get("value") in list(game_state.exits.keys()):
                        game_state.exits[direction.attrib.get("value")] = True

            return

        def component(elem):
            """ needs thought through
            """
            if elem.attrib.get("id"):
                if elem.attrib["id"] == "exp":
                    pass

            # catchall
            else:
                text_lines.put(
                    (("text", etree.tostring(elem)),)
                )  # tostring is making a bytes string
                text_lines.put(
                    (("text", elem.text),)
                )  # tostring is making a bytes string

        def pushBold(elem):
            """ change this line to a color preset, can hardcode for now
            """
            # text_lines.put((('text', etree.tostring(e)),)) # tostring is making a bytes string
            return

        def popBold(elem):
            """ xml element is not used
            """
            logging.info("popBold: " + repr(elem.attrib))
            return

        def popStream(elem):
            """ xml element is not used
            """
            logging.info("popStream: " + repr(elem.attrib))
            return

        def pushStream(elem):
            """
            this xml element needs to grab more lines until it finds <popStream/>
            notably used for streamWindow / id='inv' on startup
            """
            if elem.attrib.get("id"):
                DEBUG_PREFIX = (
                    bytes(elem.tag, "ascii")
                    + b":"
                    + bytes(elem.attrib["id"], "ascii")
                    + b": "
                )

                if elem.attrib["id"] in ("logons", "atmospherics"):
                    if elem.tail:
                        text_lines.put("text", elem.tail)
                elif elem.attrib["id"] == "percWindow":
                    pass
                elif elem.attrib["id"] == "combat":
                    if elem.tail:
                        text_lines.put("text", elem.tail)
                elif elem.attrib["id"] in ("talk", "whispers", "thoughts"):
                    pass
                elif elem.attrib["id"] in ("group"):
                    pass
                # does not yet pass all text contents, which we want...
                elif elem.attrib["id"] in ("inv"):
                    pass
                # catchall for elements WITH 'id' attr
                else:
                    text_lines.put(
                        (("text", DEBUG_PREFIX + etree.tostring(elem)),)
                    )  # tostring is making a bytes string

            # catchall
            else:
                text_lines.put(
                    (("text", b"pushStream: " + etree.tostring(elem)),)
                )  # tostring is making a bytes string

            return

        def streamWindow(elem):
            """ room and other stuff
            """

            if elem.attrib.get("id"):
                if elem.attrib["id"] == "main":
                    return
                if elem.attrib["id"] == "room":
                    return
                    # covered by the room text
                    '''
                    text_lines.put(
                        (
                            (
                                "text",
                                bytes(
                                    elem.attrib["title"] + elem.attrib["subtitle"],
                                    "ascii",
                                ),
                            ),
                        )
                    )
                    '''

            # catchall
            else:
                text_lines.put(
                    (("text", b"pushStream: " + etree.tostring(elem)),)
                )  # tostring is making a bytes string

            return

        def clearStream(elem):
            """ xml element is not used
            """
            # text_lines.put((('text', etree.tostring(elem)),)) # tostring is making a bytes string
            return

        def roundTime(elem):
            """
            """
            # if they forget roundTime 'value', then we don't update the state
            if elem.attrib.get("value"):
                game_state.roundtime = int(elem.attrib.get("value"))
            return

        def prompt(elem):
            """
            """
            # if they forget time, then we don't update the state
            if elem.attrib.get("time"):
                game_state.reported_time = int(elem.attrib.get("time"))
                game_state.time = game_state.reported_time
            return

        def preset(elem):
            """
            """
            if elem.attrib.get("id"):
                DEBUG_PREFIX = (
                    bytes(elem.tag, "ascii")
                    + b":"
                    + bytes(elem.attrib["id"], "ascii")
                    + b": "
                )
                if elem.attrib["id"] == "speech":
                    if elem.text:
                        # TODO - this pattern works, but we should write a wrapper function for all these reprs between them and text_lines.put()
                        # ALSO is this better than etree.tostring?
                        #text_lines.put((("text", bytes("".join(elem.itertext()), 'ascii')),))
                        text_lines.put(textbox_wrapper(bytes("".join(elem.itertext()), 'ascii')))
                        #text_lines.put((("text", bytes(elem.text, "utf-8")),))
                    pass
                elif elem.attrib["id"] == "roomDesc":
                    if not elem.text:
                        return
                    logging.info(b"room text: " + etree.tostring(elem))
                    # logging.info(b"room text: " + bytes(elem, 'ascii'))
                    line = (('text', bytes("".join(elem.itertext()).strip()+str(elem.tail or ""), 'ascii')),)
                    text_lines.put(line)
                    # why use this?
                    #text_lines.put((("text", etree.tostring(elem)),))
                # attrib == id catchall
                else:
                    text_lines.put(
                        (("text", DEBUG_PREFIX + etree.tostring(elem)),)
                    )  # tostring is making a bytes string

            # catchall
            else:
                text_lines.put(
                    (("text", b"preset no id:" + etree.tostring(elem)),)
                )  # tostring is making a bytes string
            return

        def dialogData(elem):
            """
            """
            if elem.attrib.get("id"):
                if elem.attrib["id"] == "minivitals":
                    pass
                # attrib == id catchall
                else:
                    text_lines.put(
                        (("text", etree.tostring(elem)),)
                    )  # tostring is making a bytes string

            # catchall
            else:
                text_lines.put(
                    (("text", etree.tostring(elem)),)
                )  # tostring is making a bytes string
            return

        def style(elem):
            """
            """
            if elem.attrib.get("id"):

                if elem.attrib["id"] == "roomName":
                    pass
                if not elem.attrib["id"] or elem.attrib["id"] == "" or elem.attrib["id"] is None:
                    pass

            # catchall
            else:
                if elem.text:
                    text_lines.put(
                        (("text", b"style: " + etree.tostring(elem)),)
                    )  # tostring is making a bytes string
            return

        def resource(elem):
            """
            """
            if elem.attrib.get("picture"):
                pass

            # catchall
            else:
                text_lines.put(
                    (("text", etree.tostring(elem)),)
                )  # tostring is making a bytes string
            return

        # you would use if statements on the attribs inside
        # attribs can always be passed as elem.attrib in this format
        xml_actions = {
            "roundTime": roundTime,
            "prompt": prompt,
            "popStream": popStream,
            "compass": compass,
            "component": component,
            "resource": resource,
            "preset": preset,
            "style": style,
            "dialogData": dialogData,
            # if i enable pushstream then it eats up the rest of the input
            # this is just one example of how i need to redo the xml parsing
            "pushStream": pushStream,
            "streamWindow": streamWindow,
            "clearStream": clearStream,
            "popBold": popBold,
            "pushBold": pushBold,
        }

        # run the function at e.tag
        # if there isn't a tag just skip it...
        if xml_actions.get(e.tag, None):
            logging.info("found function for {}: {}".format(e.tag, xml_actions[e.tag]))
            try:
                xml_actions[e.tag](e)
            # we need to globally handle exceptions gracefully without crashing
            # i think this raise will eventually pass the exception up to the handler
            except Exception as exc:
                raise exc
        else:
            # interestingly, this is still getting child xml to parse...
            # even though the xml feeder is still correctly feeding it inside the parent
            # intentionally still passing: popBold
            # for now: put all xml lines not in xml_actions
            logging.info(b"XML Parse Failed:RAW=" + etree.tostring(e))
            # text_lines.put((('text', b'RAW:' + etree.tostring(e)),)) # tostring is making a bytes string
            # we could do something custom here, like log the missing xml_action for later use
            pass

        # is this universally true?
        if e.tail:
            text_lines.put((("text", "tail: " + e.tail.encode("utf-8")),))

    return root_element, still_parsing


def process_game_xml(preprocessed_lines, text_lines, game_state):
    """ Get any game state out of the XML, return a replacement line

    We now want to process any XML line fully as xml using the obj.text and obj.tail values
    to retrieve text.

    RULE:
        1. If a line starts with XML it is XML
        2. Otherwise, it is text.

    This RULE greatly simplifies parsing and removes us from split text/xml lines.

    It's a complicated rewrite, but should present a flatter control flow.

    Some XML elements are always multiline and we want to be able to parse those as a single glob.

    The failure state (xml not processed) should leave the XML in the display, so the
    player can report the issue and work around it without missing an important detail.

    """
    # Queue.get() blocks by default
    op_line = preprocessed_lines.get()

    # don't process if it doesn't start with XML
    # this may not be a hard and fast rule, mid-line XML might be a thing
    # if so update this control flow
    if op_line and op_line[0][0] != "xml":

        try:
            line = op_line[0][1].decode("utf-8")

            # don't use this to trigger the command queue, use the global roundtime time
            pattern_command_failed = r"\.\.\.wait ([0-9]+) seconds\."
            command_failed = re.fullmatch(pattern_command_failed, line)

            # you can imagine how this would fail if 2 commands were submitted back to back
            # so it's not this simple, we need to be able to give commands some index
            # but lets not YET add a bigger data structure for each command in the command history - YET
            if command_failed:
                failing_command = game_state.command_history.get()
                logging.info(b"Command failed from RT: " + failing_command)
                game_state.rt_command_queue.put(failing_command)
                # put it back on the history too, it still was submitted
                # otherwise on subsequent fails, we start getting offset
                # history should be write only, is there a better queue action?
                game_state.command_history.put(failing_command)
        except Exception as e:
            logging.info("failed: ", e)

        text_lines.put(op_line)

        return

    # i think there are some multiline xml objects, need to review the TCP dumps
    # if so, we can just say "if still_parsing: op_line.append(preprocessed_lines.get())
    # this is a straightforwards way to get a multiline string.
    # it doesn't solve hypothetical cases where a self-closing tag has text after and then
    # another self-closing tag symbolizes the end of that text.  - catalog these manually!
    # run each line as its own xml... but this is a disaster as some have closing tags!
    linenum = 0
    while linenum < len(op_line):

        nextline = op_line[linenum][1]

        # only feed the line if it starts with xml... is this universally true?
        if op_line[linenum][0] == "xml":

            """
            # identify if the root xml element has a text tail. if so, append it.
            # this allows us to munge the text element.tail in the element's 'action' function
            # *** needs doing *** warning: only self-closing tags have text tails... how to manage this?
            # *** could label self closing elements in the splitter differently...
            # *** note: since non-self-closing-elements never have a tail, this "should not" break things...
            if linenum+1 < len(op_line) and op_line[linenum+1][0] == 'text':
                linenum += 1
                tail = op_line[linenum][1]
                nextline += tail
            """

            events = (
                "start",
                "end",
            )  # other events might be useful too? what are my options?
            parser = etree.XMLPullParser(
                events, recover=True
            )  # can we log recoveries somewhere?

            # feed lines until the root element is closed
            root_element = None
            still_parsing = True
            while still_parsing and linenum < len(op_line):

                # the initial nextline is already set up, see directly above
                if not nextline:
                    nextline = op_line[linenum][1]  # same as line, but used/incremented in this while loop
                parser.feed(nextline)

                # examine the parser and determine if we should feed more lines or close...
                root_element, still_parsing = parse_events(
                    parser, root_element, still_parsing, text_lines, game_state
                )

                # avoid double increment in parent while loop
                if still_parsing:
                    linenum += 1

                nextline = b""

            # parser.close() # i think this is recommended... read about it, it is probably gc'd next loop?

        # if the line is text...
        else:
            text_lines.put((op_line[linenum],))

        linenum += 1

        # feed another line if still parsing
        # probably need a cap on how many times we will do this before dumping the xml and moving on
        if linenum >= len(op_line) and still_parsing:
            op_line.append(preprocessed_lines.get())

    ## once the line is processed, trigger all queued xml events for the line?
    ## we can also trigger the xml events as they come up...

    return
