''' Get a token from a login and password

EAccess Protocol: http://warlockclient.wikia.com/wiki/EAccess_Protocol

SGE Protocol: https://gswiki.play.net/SGE_protocol/saved_posts
'''
import socket
import time

from config import *

def setup_game_connection(host, port, server_login_token, frontend_settings):

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = (host, int(port))
    sock.connect(server)

    time.sleep(1) # would be better to get an ACK of some sort before sending the token...

    sock.sendall(b'K\n') # request a key

    tcp_buffer = bytes()
    while b'\n' not in tcp_buffer:
        tcp_buffer += sock.recv(64)

    pw_hashing_key, _sep, _tail = tcp_buffer.partition(b'\n')

    print("hashkey : ", pw_hashing_key)
    print("password: ", password)
    _pass_ints = [l for l in password]
    _key_ints = [l for l in pw_hashing_key]
    print("_pass_ints: ", _pass_ints)
    print("_key_ints : ", _key_ints)
    _xor_ints = [p ^ k for p, k in zip(_pass_ints, _key_ints)]
    print("xor_ints  : ", _xor_ints)

    #pass_decremented = [(int.from_bytes(b'l', byteorder='big') - 20) for l in password]
    #pass_decremented = [(l - 32) for l in password]
    #print("pass decremented", pass_decremented)
    hashed_password = list()
    for i, letter in enumerate(password):
        # bytes yield an int if you index them
        # needs python 3
        # for some reason I get values > 128
        # print(int.from_bytes(pw_hashing_key[i:i+1], byteorder='big')) # same as indexing
        # print(pw_hashing_key[i])

        # from warneck; warneck's 2 sources are:
        # 1. https://www.reddit.com/r/dragonrealms/comments/4xhcb5/stepbystep_guide_on_connecting_to_dr_via_blowtorch/
        # 2. https://github.com/jrhz/tf-dr/blob/master/DRlogin
        xor_letter = pw_hashing_key[i] ^ letter
        if pw_hashing_key[i] >= ord('a'): # 'a' is 97
            xor_letter = xor_letter ^ 64 # 64 == 0x40
        if xor_letter < ord(' '): # ' ' space is 32
            xor_letter = xor_letter | 128 # 128 == 0x80
        hashed_password.append(xor_letter)
        #hashed_password.append((pw_hashing_key[i] ^ (password[i] - 32)) + 32)
    

    print("hashed_pw_list: ", hashed_password)
    #hashed_password = b''.join([bytes(chr(l), 'ascii') for l in hashed_password])
    # bytes 'ascii' chokes on chr(l) if l > 127. need to concatenate...
    # or try another encoding that supports windows hex type 128-255 (didnt get KEY but doesnt mean it failed)
    # how about 'latin1' encoding
    #hashed_password = b''.join([bytes(chr(l), 'latin1') for l in hashed_password])

    # really hashed_password should already be convertible to bytes() as it is a seq of ints
    # consider moving all this processing to a bytearray for simplicity
    hashed_password = bytes(hashed_password)
    print("hashed_pw_bytes: ", hashed_password)
    
    sock.sendall(b'A\t' + username + b'\t' + hashed_password + b'\n') # request a key

    tcp_buffer = bytes()
    while b'\n' not in tcp_buffer:
        tcp_buffer += sock.recv(64)

    response, _sep, _tail = tcp_buffer.partition(b'\n')

    print(b'this response should have the string \\tKEY\\t in it: ' + response)
    print(_sep, _tail)


    sock.sendall(b'M\n') 
    
    tcp_buffer = bytes()
    while b'\n' not in tcp_buffer:
        tcp_buffer += sock.recv(64)

    print(b'raw_response: ' + response)

    response, _sep, _tail = tcp_buffer.partition(b'\n')

    print(b'this response should have instancecodes and instancenames:' + response)

    return sock


if __name__ == '__main__':
    ''' Get a token for the game

    ACCOUNT, GAME, CHARACTER - these must all be provided... probably just in config
    '''
    eaccess_sock = setup_game_connection(eaccess_host, eaccess_port, username, password)


