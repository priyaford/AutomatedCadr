import paho.mqtt.client as mqtt
from Crypto.Cipher import AES
from bluepy import btle
from bluepy.btle import Scanner, DefaultDelegate, Peripheral
import binascii
import os
import time


from . import bleconnecterClasses as cls
from . import bleconnecterFunctions as fxn


client = mqtt.Client()
client.on_connect = fxn.onConnect
client.on_message = fxn.onMessage
client.connect("127.0.0.1", 1883)
client.loop_start()


bleDevicesFound = {}
completeLocalNameAdtype = 9

#imeiNumber = int.from_bytes(imei, byteorder='big')
#print(imeiNumber)

#add loop for adding multiple imei
client.publish("status", "Starting scanner")
client.subscribe("bleControl/reset")
client.subscribe("bleControl/factoryReset")
client.subscribe("bleControl/toggleSiren")
client.subscribe("bleControl/wakeup")
client.subscribe("bleControl/dummy")

scanner = Scanner().withDelegate(cls.ScanDelegate())


while True:    
    devices = {}
    try: 
        client.publish("scanner", "Scanning")
        devices = scanner.scan(5.0)  
    except Exception as err:
        print("Error 9") 
        print(err)
        client.publish("errors", "Scanner error, reboot")
        time.sleep(30)
        os.system("sudo reboot")
        exit()
    for dev in devices:
        localName = dev.getValueText(9) 
        #print("Device %s (%s), RSSI=%d dB  localname:%s " % (dev.addr, dev.addrType, dev.rssi, localName))
        if localName == "   ":
            print("found ", str(dev.addr))
            client.publish("devices", localName + " " + str(dev.addr) + " " + str(dev.rssi))
            try:
                client.publish("status", "bluetooth action: " + str(dev.addr) + " " + str(dev.rssi))
                fxn.doBluetooth(dev.addr, "bleControl/wakeup")
            except Exception as err:
                print("Error 7") 
                print(err)
                break
            #print(desc, value)
            #print(text, sdid)
        if localName == "bikefinder Test":
            client.publish("devices", "device already completed " + str(dev.addr) + " " +str(dev.rssi) )
    if not cls.queue.empty():
        topic = cls.queue.get_nowait()
        if topic:
            payload = cls.queue.get()
            client.publish("status", payload + " " + topic)
            try:
                fxn.doBluetooth(payload, topic)
            except Exception as e:
                print("Error 10") 
                print(e)
                client.publish("errors", "Bluetooth error")
                #error with doing bluetooth
client.publish("status", "Exiting")
exit()

