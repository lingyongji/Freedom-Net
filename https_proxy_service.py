import socket
import json
import time
from datetime import datetime
from threading import Thread
import sys
import getopt

BUFFER_SIZE = 4096

LISTENER_IPV4 = ('0.0.0.0', 8888)
LISTENER_IPV6 = ('::', 8889)

AIM_LOCAL = 1
AIM_PROXY = 2

ip_version = 4


class Proxy(object):

    def __init__(self):
        self.server_mode = AIM_PROXY

    def run_proxy(self, mode):
        self.append_log('proxy start')
        self.server_mode = mode

        try:
            proxy_v4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_v4.bind(LISTENER_IPV4)
            listener_v4 = Thread(target=self.proxy_listen, args=[proxy_v4])
            listener_v4.setDaemon(True)
            listener_v4.start()
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

        try:
            proxy_v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            proxy_v6.bind(LISTENER_IPV6)
            listener_v6 = Thread(target=self.proxy_listen, args=[proxy_v6])
            listener_v6.setDaemon(True)
            listener_v6.start()
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

        hours = 1
        while True:
            time.sleep(3600)
            self.append_log('proxy run {0} hour(s)'.format(hours))
            hours += 1

    def proxy_listen(self, proxy):
        proxy.listen(20)
        while True:
            client, addr = proxy.accept()

            req_send = Thread(target=self.send_request, args=[client, addr])
            req_send.setDaemon(True)
            req_send.start()

    def send_request(self, client, addr):
        try:
            client = self.check_auth(client, addr)
            if not client:
                return

            family = client.family
            if ip_version == 4:
                family = socket.AF_INET
            service = socket.socket(family, socket.SOCK_STREAM)

            header = client.recv(BUFFER_SIZE).decode()
            header_items = header.split('\r\n')
            connect_index = header_items[0].find('CONNECT')
            host = ''
            if connect_index < 0:  # http proxy
                host_index = header.find('Host:')
                get_index = header.find('GET http')
                post_index = header.find('POST http')
                if host_index > -1:
                    rn_index = header.find('\r\n', host_index)
                    host = header[host_index+6:rn_index]
                elif get_index > -1 or post_index > -1:
                    host = header.split('/')[2]
                else:
                    client.close()
                    self.append_log('host parsing failed')
                    return

                host_items = host.split(':')
                host = host_items[0]
                if len(host_items) == 2:
                    port = host_items[1]
                else:
                    port = 80

                service.connect((host, int(port)))
                service.sendall(header.encode())

            else:  # https proxy
                host = header_items[0][connect_index+8:].split(':')[0]

                service.connect((host, 443))
                client.sendall(b'HTTP/1.0 200 Connection Established\r\n\r\n')

        except Exception as ex:
            self.append_log(str(ex) + host, sys._getframe().f_code.co_name)
            client.close()
            return

        self.append_log('connect to [{0}]'.format(host))

        bridge1 = Thread(target=self.bridge, args=[client, service, False])
        bridge2 = Thread(target=self.bridge, args=[service, client, True])
        bridge1.setDaemon(True)
        bridge2.setDaemon(True)
        bridge1.start()
        bridge2.start()

    def check_auth(self, client, addr):
        try:
            if self.server_mode == AIM_LOCAL:
                if client.recv(1) == b'1':
                    client.sendall(b'1')
                    return client
            else:
                token = client.recv(50).decode().split(';_;_;')
                with open('config_proxy_auth.json', 'r') as f:
                    auth = json.load(f)
                for u in auth:
                    if u['name'] == token[0] and u['pwd'] == token[1]:
                        client.sendall(b'1')
                        return client
                client.sendall(b'0')
                client.close()
                self.append_log('{0}:{1} auth failed'.format(addr[0], addr[1]))
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)
            client.close()

    def bridge(self, recver, sender, s_to_c):
        try:
            while True:
                data = recver.recv(BUFFER_SIZE)
                if not data:
                    if s_to_c:
                        recver.close()
                        sender.sendall(b'')
                    break
                sender.sendall(data)
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

    def append_log(self, msg, func_name=''):
        dt = str(datetime.now())
        with open('proxy.log', 'a') as f:
            f.write('{0} |S| {1} | {2} \n'.format(dt, str(msg), func_name))


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hi:', ['help', 'ipv='])
    except getopt.GetoptError:
        print('-i <ip version>')
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print('-i <input ip version>')
            sys.exit()
        if opt in ('-i', '--ipv'):
            ip_version = int(arg)

    Proxy().run_proxy(AIM_PROXY)
