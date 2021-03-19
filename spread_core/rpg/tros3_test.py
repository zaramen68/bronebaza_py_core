from spread_core.mqtt.variables import VariableTRS3, VariableReader
import paho.mqtt.client

topId = 44
num =55
value =245

mqttc = paho.mqtt.client.Client()

mqttc.username_pw_set('admin', 'broker')
# mqttc.connect('127.0.0.1', 1883)

out = VariableTRS3(None, topId, num, value, invalid=True)
pack = out.pack()
inpack = VariableTRS3(VariableReader(pack))
outList = list(pack)
out1 = VariableTRS3(None, topId, num, value, invalid=False)
pack1 = out1.pack()
inpack1 = VariableTRS3(VariableReader(pack1))
outList1 = list(pack1)
out2 = VariableTRS3(None, topId, num, val=None, invalid=True)
pack2 = out2.pack()
inpack2 = VariableTRS3(VariableReader(pack2))
outList2 = list(pack2)
out3 = VariableTRS3(None, topId, num, val=None, invalid=False)
pack3 = out3.pack()
inpack3 = VariableTRS3(VariableReader(pack3))
outList3 = list(pack3)
print('')

# mqttc.publish(topic='vtrs3', payload=pack, qos=1, retain=True)

