#imports
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import paho.mqtt.client as mqtt
import os

from . import controllerFunctions as fxn
from . import controllerClasses as cls
from ..functions import commonFunctions as comFxn


def RunController(config):

    client = mqtt.Client()
    client.on_connect = fxn.onConnect
    client.on_message = fxn.onMessage
    client.connect("127.0.0.1", 1883)
    client.loop_start()

    client.publish("Controller/log", "starting controller")
    client.subscribe("Scanner/device")
    while True:
        while not cls.controllerQ.empty():
            try:
                device = cls.Device()
                device = cls.controllerQ.get()
                #get stage
                #send to scanner
                doc = config.db.document(u'devices' + '/' +device.deviceId).get()
                try:
                    enabledTest = doc.get(u'config.enableSystemTest')
                    if enabledTest == False:
                        continue
                    stage = doc.get(u'systemTest.stage')
                except:
                    continue
                if not stage: 
                    continue
                if stage.startswith("accelerometerTest/triggerMovement"):
                    msg = "Triggering movement for  " + device.bleAddr
                    client.publish("Controller/movement", msg)
                    continue
                if stage.startswith("bleControl/wakeup"):
                    if device.eventLoop == "stayAwake" or device.eventLoop == "lightSleep" or device.eventLoop == "deepSleep":
                        client.publish(stage, device.bleAddr +" "+ device.deviceId)
                    continue
                if stage.startswith("bleControl/oad"):
                    if int(device.battery) <30:
                        comFxn.Debug("Controller", "battery Too low on ", device.bleAddr, " id: ", device.deviceId)
                        continue
                    client.publish(stage, device.bleAddr +" "+ device.deviceId)
                    continue
                if stage.startswith("bleControl"):
                    ready = doc.get(u'systemTest.bleTest.readyForAction')
                    if ready == True:
                        client.publish(stage, device.bleAddr +" "+ device.deviceId)
                    continue        
            except Exception as err:
                comFxn.Debug("Controller")
                comFxn.Debug(err)        
        



'''
document---deviceId |-systemTest(coll) -    type:
                    |                       timestamp:
                    |                       event:
                    |                       result:
                    |
                    |_systemTest(var) |-
                                      |-stage:
                                      |-result {}
'''

#start testing loop

#System test

#Check that devide is in internalName == testdevice
#Make logfile from date and imei
#get deviceinfo from firebase
#Print DeviceId and Imei to file
#print Versions to file

#Open bluetooth, ensure device is on bluetooth




'''
test sleep function:
    set debug mode
    set enableSkipGps to true
    set deepsleepduration to 1 minute
    reset device
    wait for init packet
    wait for position packet
    Wait for two minutes
    success/fail log
    test:
        deepsleep
        lightsleep
        stayawake
        kombinasjoner
'''

'''
    Legg enhet i sleep modus
    en tid etter posisjonspakken aktiveres bevegelse
    sjekk pakken som har kommet inn
    accelerometer
        stayawake
        lightsleep
        sjekk movement bit
'''
'''
Encryptionkey
    sett kort oppdateringsintervall
    sett timestamp for siste pakken
    sett keys.encryption2
    sjekk log for xxxxxxxx  er satt
'''

'''
Posisjonstest:
Sjekk posisjoner mot standarder for:
    - temperatur
    - snr
    - satelliter
    - battery level
    - Longitude
    - Latitude
    - charging kontroller strøm til enheter
    - cellid
    - lac
    - mcc
    - mnc
    - versjoner
'''


'''Langkjør:
   - sett på en standard soveperiode
    - sjekk at pakker kommer inn til riktig tidspunkt
   - bevegelsesscenario
   - normalt sovescenario
    '''

'''
#Test Bluetooth
#    - Reset
#        kjør reset, sjekk at bluetooth går gjennom og enheten er tilgjengelig etter noen sekunder igjen
#    - Factory Reset
#        kjør factory reset med charging off
#        sjekk at enhet forsvinner fra bluetooth
#        start charger
#    - Powerdown
#    - Wakeup
'''
