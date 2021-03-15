from spread_core.mqtt.variables import VariableTRS3, VariableReader
import paho.mqtt.client

topId = 4
num =5
value =245
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
mqttc.loop_forever()


# mqttc.publish(topic='vtrs3', payload=pack, qos=1, retain=True)

