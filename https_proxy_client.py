import socket
import json
from datetime import datetime
from threading import Thread
from win_proxy_setting import set_proxy_config, back_proxy_config
from https_proxy_service import Proxy, BUFFER_SIZE, AIM_LOCAL, AIM_PROXY
import sys

LISTENER = ('localhost', 7777)
LOCAL_PROXY = ('localhost', 8888)


class Client(object):

    def run_client(self):
        set_proxy_config()
        back = Thread(target=self.back_proxy_setting)
        back.setDaemon(True)
        back.start()

        run_client = Thread(target=self.client_listen)
        run_client.setDaemon(True)
        run_client.start()

        Proxy().run_proxy(AIM_LOCAL)

    def back_proxy_setting(self):
        input('input any key to exit\n')
        back_proxy_config()
        self.append_log('client closed')
        import os
        os._exit(0)

    def client_listen(self):
        self.append_log('client start')
        local = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        local.bind(LISTENER)
        local.listen(20)

        while True:
            client, addr = local.accept()

            req_send = Thread(target=self.send_request, args=[client])
            req_send.setDaemon(True)
            req_send.start()

    def send_request(self, client):
        request = client.recv(BUFFER_SIZE)
        if not request:
            client.close()
            return

        proxy_aim = self.check_aim(request.decode())
        if not proxy_aim:
            client.close()
            return

        proxy = self.connect_proxy(proxy_aim)
        if not proxy:
            client.close()
            self.append_log('connect proxy failed')
            return

        try:
            proxy.sendall(request)

        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)
            client.close()
            return

        bridge1 = Thread(target=self.bridge, args=[client, proxy, True])
        bridge2 = Thread(target=self.bridge, args=[proxy, client, False])
        bridge1.setDaemon(True)
        bridge2.setDaemon(True)
        bridge1.start()
        bridge2.start()

    def check_aim(self, header):
        try:
            header_items = header.split('\r\n')
            connect_index = header_items[0].find('CONNECT')
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
                    self.append_log('host parsing failed')

                host_items = host.split(':')
                host = host_items[0]
            else:  # https proxy
                host = header_items[0][connect_index+8:].split(':')[0]

            with open('ip.txt', 'r') as f:
                for ip in f:
                    if host.find(str(ip).strip()) >= 0:
                        self.append_log('request {0} by proxy'.format(host))
                        return AIM_PROXY
            return AIM_LOCAL
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

    def connect_proxy(self, proxy_aim):
        try:
            if proxy_aim == AIM_LOCAL:
                proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                proxy.connect(LOCAL_PROXY)
                proxy.sendall(b'1')
                if proxy.recv(1) == b'1':
                    return proxy
                else:
                    proxy.close()
            else:
                with open('config_client_vps.json', 'r') as f:
                    auth = json.load(f)
                for u in auth:
                    if bool(u['used']):
                        family = socket.AF_INET
                        if (u['ipv']) == 6:
                            family = socket.AF_INET6
                        proxy = socket.socket(family, socket.SOCK_STREAM)
                        proxy.connect((u['ip'], u['port']))
                        token = '{0};_;_;{1}'.format(u['name'], u['pwd'])
                        proxy.sendall(token.encode())
                        if proxy.recv(1) == b'1':
                            return proxy
                        else:
                            self.append_log('{0} auth failed'.format(['ip']))
                            proxy.close()
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

    def bridge(self, recver, sender, c_to_s):
        try:
            while True:
                data = recver.recv(BUFFER_SIZE)
                if not data:
                    if c_to_s:
                        recver.close()
                        sender.close()
                    break
                sender.sendall(data)
        except Exception as ex:
            recver.close()
            sender.close()
            return
            # self.append_log(ex, sys._getframe().f_code.co_name)

    def append_log(self, msg, func_name=''):
        dt = str(datetime.now())
        with open('proxy.log', 'a') as f:
            f.write('{0} |C| {1} | {2} \n'.format(dt, str(msg), func_name))


if __name__ == '__main__':
    Client().run_client()
