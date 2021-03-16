from spread_core.mqtt.variables import VariableTRS3, VariableReader
import paho.mqtt.client

topId = 455
num =2
value =False
topic = 'Tros3/State/2434/Equipment/DimmingLight/635561/0'
topic1 = 'Tros3/State/2434/Equipment/#'

def on_message(mqttc, userdata, msg):
    inpack = VariableTRS3(VariableReader(msg.payload))
    out=inpack

mqttc = paho.mqtt.client.Client()


mqttc.username_pw_set('admin', 'broker')
mqttc.on_message = on_message

mqttc.connect('10.10.1.211', 1883)
mqttc.subscribe(topic1, qos=1)

out = VariableTRS3(None, topId, num, value)
pack = out.pack()
out1 = VariableTRS3(None, topId, num, val=value, invalid=True)
pack1 = out1.pack()

out2 = VariableTRS3(None, topId, num, val=None)
pack2 = out2.pack()
out3 = VariableTRS3(None, topId, num, val=None, invalid = True)
pack3 = out3.pack()

mqttc.loop_forever()
# mqttc.publish(topic='vtrs3', payload=pack, qos=1, retain=True)

