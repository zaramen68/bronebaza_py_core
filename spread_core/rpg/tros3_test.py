from spread_core.mqtt.variables import VariableTRS3, VariableReader
import paho.mqtt.client

topId = 4
num =5
value =245

mqttc = paho.mqtt.client.Client()

mqttc.username_pw_set('admin', 'broker')
mqttc.connect('127.0.0.1', 1883)

out = VariableTRS3(None, topId, num, value)
pack = out.pack()
inpack = VariableTRS3(VariableReader(pack))

mqttc.publish(topic='vtrs3', payload=pack, qos=1, retain=True)

