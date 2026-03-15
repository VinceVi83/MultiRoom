from Gestion import Interpretation
import socket
import select
CONNECTION_LIST = []
RECV_BUFFER = 4096
RPI_PORT = 8888

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(("127.0.0.1", RPI_PORT))
server_socket.listen(10)

CONNECTION_LIST.append(server_socket)

send = ''
ip_master = '127.0.0.1'

while 1:
    read_sockets, write_sockets, error_sockets = select.select(CONNECTION_LIST, [], [])

    for sock in read_sockets:
        if sock == server_socket:
            sockfd, addr = server_socket.accept()
            CONNECTION_LIST.append(sockfd)
            ip_cli, port = addr

        else:
            ip_cli, port = addr
            try:
                data = sock.recv(RECV_BUFFER)
            except:
                print("Client (%s, %s) is offline", addr)
                sock.close()
                CONNECTION_LIST.remove(sock)
                continue
            if ip_cli == ip_master:
                returnVal = Interpretation.cmdRPI()
                if returnVal == 1:
                    send = 'done'
                if returnVal == -1:
                    send = 'erreur'
                if returnVal == 0:
                    send = "Command doesn't exist"
            else:
                send = 'You are not my master !!!'
                data = 'fin'.encode()

                sock.send(send.encode())

            if data.decode() == 'fin':
                sock.close()
                CONNECTION_LIST.remove(sock)
                print("Client (%s, %s) is offline", addr)
                continue
