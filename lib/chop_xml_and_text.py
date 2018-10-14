''' A rudimentary xml tag parser for identifying where XML might start.

The parser expects to return the raw XML if parse fails.

There are situation where this process is too rudimentary.

e.g. a player can use < in their free text 'chat' which could impact talk, whisper, etc.
'''

def chop_xml_and_text_from_line(line):
    ''' Given a line chop it into xml and text sections

    returns a list of tuples in the format: [(type_string, content_string), ...]
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


