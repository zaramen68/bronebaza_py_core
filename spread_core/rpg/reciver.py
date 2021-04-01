from spread_core.rpg.protocol import *
from spread_core.rpg.settings import *


def listen_rpg1(sock, mqttc, canQue, daliQue, modBusQue, diQue, diEvent):


    while True:

        try:
            out = sock.recive_data()

        except BaseException as ex:
            # logging.exception(ex)
            mqttc.publish(topic=topic_dump.format(PROJECT) + '/error', payload=str(ex))
        else:
            if out is not None:

                # rsvTime = time.time()
                rsvTime = current_milli_time()
                while len(out) > 0:
                    rpgData, rest = parceData(out)
                    if hex(rpgData['opCode']) == OPCODECANDATA:

                        parceCAN(rsvTime, daliQue, modBusQue, diQue, diEvent, rpgData['payloadCAN'])

                        # print('===={0}========={1}========'.format(hex(rpgData['payloadCAN']['canId'][0]), hex(rpgData['payloadCAN']['canId'][1])))
                    elif hex(rpgData['opCode']) == OPCODEPINGREQ:
                        print("04 00 00 00")
                        canQue.put_nowait(rpgData['payloadLen'])
                    elif hex(rpgData['opCode']) == OPCODECONNECT:
                        print("RPG GATEWAY IS CONNECTED")
                        canQue.put(rpgData['payload'])
                    if len(rest) == 0:
                        break
                    out = out[(len(out) - len(rest)):]
        # qFlag.value = False
        #
        # self.mqttc.publish(topic=topic_send[1] + '/lamp', payload=str(out))
        # logging.debug('[recive from server  <-]: {}'.format(out))


def parceCAN(rsvTime, daliQue, modBusQue, diQue, diEvent, data):
    canId = bytearray(2)
    canId[0] = data['canId'][1]
    canId[1] = data['canId'][0]
    canData = bitstring.BitArray(canId)
    c = canData.bin
    addr_to = c[-5:]
    addr_from = c[:-5]
    addrIntTo = canData[-5:].uint
    addrIntFrom = canData[:-5].uint
    if addrIntTo == 31:
        #  message to gateway
        byte0 = bytearray(1)
        byte0[0] = data['data'].pop(0)
        bbyte0 = bitstring.BitArray(byte0)
        flag_res = bbyte0[1]
        t_class = bbyte0[-5:]
        n = t_class.int
        if n == 2:
            #  ModBus
            modBus = data['data']
            modBusQue.put_nowait((rsvTime, modBus))
            # modBusQue.join()
            print('===========mbus======={}'.format(str(modBus)))

        elif n == 1:
            #  Dali
            # if (current_milli_time()-self.callDaliTime)<= DALI_GAP:
            daliQue.put_nowait((rsvTime, data['data']))
            daliQue.join()
        elif n == 5:
            diEvent.set()
            diQue.put_nowait(data['data'])


def parceData(message):
    dataAr = list(bytearray(0))
    for b in message:
        dataAr.append(b)

    if hex(dataAr[0]) == OPCODECANDATA:
        data = {
            'opCode': bytearray(1),
            'payloadLen': bytearray(3),
            'payloadCAN': {
                'canId': bytearray(2),
                'dlc': bytearray(1),
                'data': bytearray()
            }
        }
        data['opCode'] = dataAr.pop(0)
        for i in range(3):
            data['payloadLen'][i] = dataAr.pop(0)

        for i in range(2):
            data['payloadCAN']['canId'][i] = dataAr.pop(0)

        data['payloadCAN']['dlc'] = data['payloadLen'][0] - 2

        for i in range(int(data['payloadLen'][0]) - 2):
            data['payloadCAN']['data'].append(dataAr.pop(0))

        return data, dataAr

    elif hex(dataAr[0]) == OPCODECONNECT:
        toconnect = {
            'opCode': bytearray(1),
            'payloadLen': bytearray(3),
            'payload': bytearray(8)
        }
        toconnect['opCode'] = dataAr.pop(0)
        for i in range(3):
            toconnect['payloadLen'][i] = dataAr.pop(0)
        for i in range(int(toconnect['payloadLen'][0])):
            toconnect['payload'][i] = dataAr.pop(0)

        return toconnect, dataAr

    elif (hex(dataAr[0]) == OPCODEPINGREG) or (hex(dataAr[0]) == OPCODEPINGREQ):
        ping = {
            'opCode': bytearray(1),
            'payloadLen': bytearray(3)
        }
        ping['opCode'] = dataAr.pop(0)
        for i in range(3):
            ping['payloadLen'][i] = dataAr.pop(0)
        return ping, dataAr
    elif hex(dataAr[0]) == OPCODEDISCONNECT:
        disconnect = {
            'opCode': bytearray(1),
        }
        disconnect['opCode'] = dataAr.pop(0)

        return disconnect, dataAr

    elif hex(dataAr[0]) == OPCODEERROR:
        error = {
            'opCode': bytearray(1),
            'payloadLen': bytearray(3),
            'error': bytearray(1)
        }
        error['opCode'] = dataAr.pop(0)
        for i in range(3):
            error['payloadLen'][i] = dataAr.pop(0)
        error['error'] = dataAr.pop(0)
        return error, dataAr
