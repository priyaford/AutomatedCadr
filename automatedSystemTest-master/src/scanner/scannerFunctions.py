from bluepy import btle
from bluepy.btle import Scanner, DefaultDelegate, Peripheral
import binascii

from . import scannerClasses as cls
from ..functions import commonFunctions as comFxn

## @scanner
bleCmd = {
    "reset" : b'\x01\x00\x01\x00\x00',
    "factoryReset" : b'\x00\x00\x02\x00\x00',
    "wakeup" : b'\x80\x00\x00\x00\x00',
    "toggleSiren" : b'\x00\x00\x09\x00\x00',
    "blepin" : b'\x2C\x28\x46\xBB\x5C\xDB\x87\xF1\x3D\xEE\x4E\x8A\x64\xFB\x4E\xCE\x65\x3F\xDB\00'
}

## Callback function for Mqtt connect event
def onConnect(client, userdata, flags, rc):
    comFxn.Debug("Scanner ", "Connected Scanner to mqtt with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("$SYS/#")          

## Checking that the advertised data has its origin from a bikefinder device, this is based on 
# Bikefinders Manufacturer code (BLE sig)
# @param text: four byte manufacturer code code
#
def checkBleManufacturer(text):
    if text[0]=='6' and text[1]=='f' and text[2]=='0'and text[3]=='5':
        return True
    return False

## Responsible for all Bluetooth action that is to be performed on the devices in test.
# Works by connecting to Device, writing pin, reading version, and writing command.
# @param device: Device object for the current device
# @param command: 
def doBluetooth(bleAddr, deviceId, command, client, db):
    msg = "bluetooth action: " + command + " on " + bleAddr + " " + deviceId
    client.publish("Scanner/log", msg)
    try:
        comFxn.Debug("Scanner ", "Connecting to device...")
        per = Peripheral(bleAddr)
        characteristic = per.getCharacteristics()
        for char in characteristic:
            if char.uuid == "3b941110-94a3-4b04-ab27-336173113a33":
                comFxn.Debug("Scanner ", "Writing characteristic commands")
                handle = char.getHandle()
                char.write(bleCmd["blepin"])
                if(char.supportsRead()):
                    data = binascii.b2a_hex(char.read())
        for char in characteristic:
            try:
                if char.uuid == "3b941130-94a3-4b04-ab27-336173113a33":
                    comFxn.Debug("Scanner ", "Reading characteristic version...")
                    handle = char.getHandle()
                    if(char.supportsRead()):
                        data = binascii.b2a_hex(char.read())
                        data = data.decode("utf-8")
                        tiVersion = data[0:2] + '.' + data[2:4] + '.' + data[4:6]
                        hwVersion = data[6:8] + '.' + data[8:10] + '.' + data[10:12]
                        mtkVersion = data[12:14] + '.' + data[14:16]
                        comFxn.Debug("Scanner ", "Versions is: ", str(tiVersion), str(mtkVersion), str(hwVersion))
            except: 
                pass
        for char in characteristic:
            if char.uuid == "3b941080-94a3-4b04-ab27-336173113a33":
                comFxn.Debug("Scanner ", "Writing characteristic commands...")
                handle = char.getHandle()
                if(char.supportsRead()):
                    data = binascii.b2a_hex(char.read())
                if command == "Manual/reset":             
                    char.write(bleCmd["reset"])
                if command == "bleControl/reset":             
                    char.write(bleCmd["reset"])
                if command == "bleControl/factoryReset":             
                    char.write(bleCmd["factoryReset"])
                if command == "bleControl/wakeup":             
                    char.write(bleCmd["wakeup"])
                if command == "bleControl/toggleSiren":             
                    char.write(bleCmd["toggleSiren"])
                if command == "bleControl/dummy":             
                    comFxn.Debug("Scanner ", "dummy")
        comFxn.Debug("Scanner ", "Done")
        data = {u'systemTest.bleTest.readyForAction':False}
        data = db.document(u'devices'+'/'+deviceId).update(data)
        msg = command  + " " + bleAddr + " pass" + " noreason " 
        client.publish("Scanner/status", msg)
        return True
    except Exception as err:
        comFxn.Debug("Scanner ", err)
        return False



    # The callback for when a PUBLISH message is received from the server.
def onMessage(client, userdata, msg):
    try:
        if msg.topic == "bleControl/reset" or msg.topic == "bleControl/factoryReset" \
            or msg.topic == "bleControl/wakeup" or msg.topic == "bleControl/toggleSiren" \
            or msg.topic == "bleControl/dummy" or msg.topic == "Manual/reset" \
            or msg.topic == "bleControl/oad":        
            payload = msg.payload.decode("utf-8")
            cls.scannerIncomingQ.put(msg.topic)
            cls.scannerIncomingQ.put(payload)
    except Exception as err:
        print(err)

