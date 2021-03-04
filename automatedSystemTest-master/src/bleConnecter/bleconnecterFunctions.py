from bluepy import btle
from bluepy.btle import Scanner, DefaultDelegate, Peripheral
import binascii

from . import bleconnecterClasses




def onConnect(client, userdata, flags, rc):
    print("Connected bleconnecter to mqtt with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("$SYS/#")          

def checkBleManufacturer(text):
    if text[0]=='6' and text[1]=='f' and text[2]=='0'and text[3]=='5':
        return True
    return False

def doBluetooth(device, command):
    per = Peripheral(device)
    characteristic = per.getCharacteristics()
    for char in characteristic:
        if char.uuid == "00002a00-0000-1000-8000-00805f9b34fb":
            data = char.read()
            print(data.decode("utf-8"))
    


    # The callback for when a PUBLISH message is received from the server.
def onMessage(client, userdata, msg):
    try:
        if msg.topic == "bleControl/reset" or msg.topic == "bleControl/factoryReset" or msg.topic == "bleControl/wakeup" \
            or msg.topic == "bleControl/toggleSiren" or msg.topic == "bleControl/dummy":        
            payload = msg.payload.decode("utf-8")
            queue.put(msg.topic)
            queue.put(payload)
    except Exception as err:
        print(err)