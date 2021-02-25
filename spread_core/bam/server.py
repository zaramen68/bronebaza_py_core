class Server:
    def __init__(self, file):
        self._ip = file['attributes']['ip']
        self._failureOffset = file['attributes']['failureOffset']
        self._port = file['attributes']['port']
        self._tickRate = file['attributes']['tickRate']
        self._type = file['type']
        self._id = file['id']
        self._key = file['key']
        self._name = file['name']
