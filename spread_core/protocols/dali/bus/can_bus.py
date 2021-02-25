import threading
from datetime import datetime

import can

from spread_core.tools.settings import logging


class CanBus:
    def __init__(self, msg_handler):
        self.bus = can.Bus(channel='can0', bustype='socketcan')
        self.msg_handler = msg_handler
        threading.Thread(target=self.listen_can).start()

    def listen_can(self):
        while True:
            try:
                for msg in self.bus:
                    addr = hex(msg.arbitration_id).replace('0x', '').rjust(3, '0')
                    pr = msg.arbitration_id & (1 << 10)             # 10000000000
                    addr_from = (msg.arbitration_id >> 5) & 0x1f    # 01111100000
                    addr_to = msg.arbitration_id & 0x1f             # 00000011111
                    if addr_from in range(1, 30):
                        class_id = msg.data[0]
                        if class_id == 0x01:
                            self.msg_handler(addr_from, msg.data[1:])
            except BaseException as ex:
                logging.exception(ex)

    def send(self, addr, msg):
        try:
            message = can.Message(arbitration_id=addr, data=msg, timestamp=datetime.now().timestamp(),
                                  extended_id=False)
            if self.bus:
                self.bus.send(message)
            else:
                logging.warning(str.format('SEND failed: {}', message))
        except BaseException as ex:
            logging.exception(ex)
