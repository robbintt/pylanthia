
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

