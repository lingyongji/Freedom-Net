import os
import json
import random
from https_proxy_service import BUFFER_SIZE


def check_key():
    if os.path.exists('key'):
        step = input('key is exist, do you want generate new key?(y/n):')
        while True:
            if step in ('y', 'Y'):
                generate_key()
                print('new key generated')
                break
            elif step in ('n', 'N'):
                print('exit')
                break
            else:
                step = input('please input (y/n):')
                continue
    else:
        generate_key()
        print('new key generated')


def generate_key():
    key = []
    for i in range(BUFFER_SIZE):
        key.append(i)
    random.shuffle(key)

    with open('key', 'w') as f:
        f.write(json.dumps(key))


if __name__ == "__main__":
    check_key()
