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

    #print(pw_hashing_key, len(pw_hashing_key))
    #print(password)
    #_pass = [l for l in password]
    #pass_decremented = [(l - 32) for l in password]
    #_key_ints = [l for l in pw_hashing_key]
    #pass_decremented = [(int.from_bytes(b'l', byteorder='big') - 20) for l in password]
    #print("_pass", _pass)
    #print("pass decremented", pass_decremented)
    #print("_key_ints", _key_ints)
    hashed_password = list()
    for i, letter in enumerate(password):
        # bytes yield an int if you index them
        # needs python 3
        # for some reason I get values > 128
        # print(int.from_bytes(pw_hashing_key[i:i+1], byteorder='big')) # same as indexing
        # print(pw_hashing_key[i])
        print(type(pw_hashing_key[i]))
        hashed_password.append((pw_hashing_key[i] ^ (password[i] - 32)) + 32)
    
    # yep I am getting 1:1
    print("pw length:", len(password))
    print("hashed pw length:", len(hashed_password))


    print("hashed_pw: ", hashed_password)
    hashed_password = b''.join([bytes(chr(l), 'ascii') for l in hashed_password])
    print(hashed_password)
    
    sock.sendall(b'A ' + username + b' ' + hashed_password + b'\n') # request a key

    tcp_buffer = bytes()
    while b'\n' not in tcp_buffer:
        tcp_buffer += sock.recv(64)

    response, _sep, _tail = tcp_buffer.partition(b'\n')

    print(b'this response should have the string \\tKEY\\t in it: ' + response)


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


