''' accrue a tcp buffer and break it into lines

This method is for processing raw tcp bytes into lines
'''
import time

def get_tcp_lines(tcp_lines, tcplog_location, gamesock, BUFSIZE=16, TCP_BUFFER_SLEEP=0.01):
    ''' receive text and xml into a buffer and split on newlines

    default buffer size is 16, 128 kind of sucks, it makes a big difference
    might be fine to try even an 8/4 byte buffer with a profiling tool

    this function does lock tcp_lines iirc
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


