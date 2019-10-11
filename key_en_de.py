import json


class Key():
    def __init__(self):
        with open('key', 'r') as f:
            key = json.load(f)
        self.key = key
        self.key_len = len(key)

    def enkey(self, meta):
        meta_len = len(meta)
        data = []
        for i in range(self.key_len):
            if self.key[i] < meta_len:
                data.append(meta[self.key[i]])
        return bytes(data)

    def dekey(self, data):
        data_len = len(data)
        meta = [None] * data_len
        index = 0
        for i in range(self.key_len):
            if self.key[i] < data_len:
                meta[self.key[i]] = data[index]
                index += 1
        return bytes(meta)
