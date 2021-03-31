
import bitstring
import time


current_milli_time = lambda: time.time() * 1000

def hex_to_bool(x):
    if x=='FE'or x=='fe' or x=='FF' or 'ff':
        return True
    elif x=='00':
        return False

def isONID(x):
    if x == 'SwitchingLight':
        return 2
    elif x == 'DimmingLight':
        return 2

def make_two_bit(x):
    bytes_list =list('00')
    list_x = list(x)
    i=-1
    while abs(i) <= len(x):
        bytes_list[i]=list_x[i]
        i=i-1
    return ''.join(bytes_list)

def make_bytes(x):
    bytes_list =list('0000')
    list_x = list(x)
    i=-1
    while abs(i) <= len(x):
        bytes_list[i]=list_x[i]
        i=i-1
    return ''.join(bytes_list)

def CanId(addrFrom, addrTo):
    addr_from_ = bitstring.BitArray(hex(addrFrom))
    addr_to_ = bitstring.BitArray(hex(addrTo))
    if addr_from_.length < 5:
        addr_from = bitstring.BitArray(5-addr_from_.length)
        addr_from.append(addr_from_)
    elif addr_from_.length >= 5:
        addr_from = addr_from_[(addr_from_.length-5):]

    if addr_to_.length < 5:
        addr_to = bitstring.BitArray(5 - addr_to_.length)
        addr_to.append(addr_to_)
    elif addr_to_.length >= 5:
        addr_to = addr_to_[(addr_to_.length - 5):]

    addr_from.append(addr_to)
    can_id = bitstring.BitArray(12 - addr_from.length)
    can_id.append(addr_from)

    return make_bytes(can_id.hex)

def ShortDaliAddtessComm(devAddr, data, cfl=0):

    devaddr = bitstring.BitArray(hex(devAddr))
    daddr = bitstring.BitArray(6 - devaddr.length)
    daddr.append(devaddr)
    addrbyte = bitstring.BitArray(bin(0))
    addrbyte.append(daddr)
    addrbyte.append(bitstring.BitArray(bin(cfl)))
    if isinstance(data, int):
        dd = addrbyte.hex + make_two_bit(hex(data).split('x')[1])
    elif isinstance(data, str):
        dd_=data.split('x')
        if len(dd_)>1:
            dd = addrbyte.hex + make_two_bit(dd_[1])
        else:
            dd = addrbyte.hex + make_two_bit(dd_[0])
    return dd

def GroupDaliAddtessComm(groupAddr, data, cfl=0):

    devaddr = bitstring.BitArray(hex(groupAddr))
    daddr = bitstring.BitArray(6 - devaddr.length)
    daddr.append(devaddr)
    addrbyte = bitstring.BitArray(bin(1))
    addrbyte.append(daddr)
    addrbyte.append(bitstring.BitArray(bin(cfl)))
    if isinstance(data, int):
        dd = addrbyte.hex + make_two_bit(hex(data).split('x')[1])
    elif isinstance(data, str):
        dd_=data.split('x')
        if len(dd_)>1:
            dd = addrbyte.hex + make_two_bit(dd_[1])
        else:
            dd = addrbyte.hex + make_two_bit(dd_[0])
    return dd

def Byte0(clss, cmd=False):

    byte0 = bitstring.BitArray(1)
    byte0[0]=cmd

    echo = bitstring.BitArray(1)
    reserve = bitstring.BitArray(1)
    cls_ = bitstring.BitArray(hex(clss))
    if cls_.length < 5:
        cls = bitstring.BitArray(5 - cls_.length)
        cls.append(cls_)
    elif cls_.length >= 5:
        cls = cls_[(cls_.length - 5):]
    byte0.append(echo)
    byte0.append(reserve)
    byte0.append(cls)

    return byte0

def Byte1(waitAns=False, st=False):
    byte1_=bitstring.BitArray(8)
    if waitAns:
        byte1_[7]=waitAns
    if st:
        byte1_[5]=st
    byte1 = byte1_.hex

    return byte1
