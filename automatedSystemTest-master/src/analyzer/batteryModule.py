
from os import system
from firebase_admin import firestore
from . import analyzerFunctions as fxn
from ..functions import commonFunctions as comFxn
import time

#Function for handling batteryShutdown 

def NotifyEnableCharging(device, client):
    msg = device.deviceId +  " " + device.bleAddr + " Device not charging, put in charging to enable test"
    client.publish("Analyzer/log", msg)

def NotifyChargeTooHigh(device, client, batteryLevel):
    msg = device.deviceId + " " + device.bleAddr + \
        " Device charge too high: percent for charge shutdown test, please discharge before continuing test"
    client.publish("Analyzer/log", msg)

def CalculateChargeStatus(adc0, adc1):
    offset = 40  #mA offset to ensure charging correct 
    voltage = adc1-adc0
    current  = voltage/200
    comFxn.Debug("Analyzer", "Device current: " + str(current) + " mA")
    if current-offset > 0:
        comFxn.Debug("Analyzer", "Device is charging")
        comFxn.Debug("Analyzer", "Device charging with ",current)
        return 'charging'
    comFxn.Debug("Analyzer", "Device is discharging")
    return 'discharging'

def DisabledChargingStage(position, systemSettings, db, device, client):    
    #check that device is charging -> send warning if not  
    adc0 = position.get('adc0')   
    adc1 = position.get('adc1')  
    if( CalculateChargeStatus(adc0, adc1) == 'discharging'):
        temp = systemSettings.get('batteryTest.shutdown.normalHighTemp')
        data = {'systemTest.batteryTest.shutdown.stage': "chargeEnabled",
                'config.temperatureResistance.high': temp,
                'config.command': 'changeTemperatureResistance'}
        comFxn.UpdateFirebase(device.deviceId, data)
        comFxn.Debug("Analyzer", "setting pass result in disable stage")
        fxn.SetPassResult(client, device, 'systemTest.batteryTest.shutdown.timestamp', db)
        return
    comFxn.Debug("Analyzer", "device not discharging yet")
    return  

def EnabledChargingStage(position, systemSettings, db, device, client):
    #check that device is charging -> send warning if not  
    adc0 = position.get('adc0')   
    adc1 = position.get('adc1')  
    if( CalculateChargeStatus(adc0, adc1) == 'charging'):
        temp = systemSettings.get('batteryTest.shutdown.highTemp')
        data = {'systemTest.batteryTest.shutdown.stage': "chargeDisabled",
                'config.temperatureResistance.high': temp,
                'config.command': 'changeTemperatureResistance'}
        comFxn.UpdateFirebase(device.deviceId, data)
        return
    comFxn.Debug("Analyzer", "device not charging yet")
    return

def StartChargeTestStage(systemSettings, db,device):
    temp = systemSettings.get('batteryTest.shutdown.highTemp')
    data = {'systemTest.batteryTest.shutdown.stage': "chargeDisabled",
            'config.temperatureResistance.high': temp,
            'config.command': 'changeTemperatureResistance',
            'systemTest.batteryTest.shutdown.timestamp': firestore.SERVER_TIMESTAMP}
    comFxn.UpdateFirebase(device.deviceId, data)
    return

def BatteryShutdown(device, deviceDoc, systemSettings, db, client):  
    comFxn.Debug("Analyzer", "BatteryShutDown() function running", device.deviceId)  
    try:
        positions = db.collection(u'devices'+'/'+device.deviceId +'/' + u'data') \
            .order_by(u'timestamp', direction=firestore.Query.DESCENDING) \
            .limit(1) \
            .stream()    
        #check that device is charging -> send warning if not 
        thisPosition = None
        for position in positions:            
            thisPosition = position   
        isCharging = thisPosition.get('battery.isCharging')
        batteryLevel = thisPosition.get('battery.level')
        print(batteryLevel, type(batteryLevel))
        if isCharging == False:
            NotifyEnableCharging(device, client)
            return     
        if batteryLevel > 90: 
            NotifyChargeTooHigh(device, client, batteryLevel)
            return   
        testStage = deviceDoc.get('systemTest.batteryTest.shutdown.stage')
        comFxn.Debug("Analyzer", testStage, " is active")
        if testStage == "start":
            StartChargeTestStage(systemSettings, db, device)
            return
        if testStage == 'chargeEnabled':
            EnabledChargingStage(thisPosition, systemSettings, db, device, client)
            return
        if testStage == 'chargeDisabled':
            DisabledChargingStage(thisPosition, systemSettings, db, device, client)
            return       
        #check timestamp, adc0 and adc1, calculate current, and decide if charging
        #if charging ok -> set pass and set temperaturelimit again. set stage, timestamp, wait for charging.
        #if stage is ready- start over
        comFxn.Debug("Analyzer","reached end of Batteryshutdownfucntions")
    except Exception as err:
        print(err)


def BatteryTestSleep(deviceDoc, db, systemSettings, eventCounter, device,client):    
    startTime = deviceDoc.get(u'systemTest.batteryTest.sleep.timestamp')         
    startTime = time.mktime(startTime.timetuple())
    data = {u'systemTest.checkInTime': firestore.SERVER_TIMESTAMP}
    comFxn.UpdateFirebase(device.deviceId, data)
    deviceDoc = db.document(u'devices' + '/' + device.deviceId).get()
    now = deviceDoc.get(u'systemTest.checkInTime')   
    now = time.mktime(now.timetuple())
    checkTime = systemSettings.get(u'batteryTest.sleep.checkTime')
    eventLimit = systemSettings.get(u'batteryTest.sleep.limit')
    if (now-startTime) < checkTime:
        comFxn.Debug("Analyzer", (now-startTime), " too short time to check yet")
        return
    sleepTime = systemSettings.get(u'batteryTest.sleep.time')
    drainLimit = systemSettings.get(u'batteryTest.sleep.drain')          
    timestamp = deviceDoc.get(u'systemTest.batteryTest.sleep.timestamp')      
    result = CheckBatteryLevel(deviceDoc, sleepTime, drainLimit, device, timestamp, client, db)
    if result:
        data = { u'systemTest.batteryTest.sleep.counter': firestore.Increment(1)}
        comFxn.UpdateFirebase(device.deviceId, data)  
        fxn.SetPassResult(client, device,"systemTest.batteryTest.sleep.timestamp", db)
    fxn.CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)


## this is checking the Battery level draw compared to the test settings in firebase.
def CheckBatteryLevel(deviceDoc, sleepTime, drainLimit, device, timestamp, client, db):
    comFxn.Debug("Analyzer ", "CheckBatteryLevel()")
    docs = db.collection(u'devices' + '/' + device.deviceId+'/'+u'data') \
        .order_by(u'timestamp', direction=firestore.Query.DESCENDING) \
        .where(u'timestamp', ">", timestamp) \
        .limit(2) \
        .stream()
    myDocs = []
    for doc in docs:
        myDocs.append(doc)
    if fxn.CountDocs(myDocs) < 2:
        return False
    lastDoc = len(myDocs)-1
    oldBattery = myDocs[0].get(u'battery.level')
    newBattery = myDocs[lastDoc].get(u'battery.level')
    isChargingStart = myDocs[lastDoc].get(u'battery.isCharging')
    isChargingEnd = myDocs[lastDoc].get(u'battery.isCharging')
    comFxn.Debug("Analyzer", "new batt ",newBattery, " vs. old ", oldBattery)
    if isChargingStart or isChargingEnd:
        msg = "BatteryCheck fail, device is charging " + device.deviceId 
        client.publish("Analyzer/log", msg)
        return False
    if (int(newBattery)-int(oldBattery)) > drainLimit:
        return False
    return True


def BatteryTestRun(deviceDoc, device, db, systemSettings, client, eventCounter):    
    startTime = deviceDoc.get(u'systemTest.batteryTest.run.timestamp')         
    startTime = time.mktime(startTime.timetuple())
    data = {u'systemTest.checkInTime': firestore.SERVER_TIMESTAMP}
    comFxn.UpdateFirebase(device.deviceId, data)
    deviceDoc = db.document(u'devices' + '/' + device.deviceId).get()
    now = deviceDoc.get(u'systemTest.checkInTime')   
    now = time.mktime(now.timetuple())
    checkTime = systemSettings.get(u'batteryTest.run.checkTime')
    eventLimit = systemSettings.get(u'batteryTest.run.limit')
    if (now-startTime) < checkTime:
        comFxn.Debug("Analyzer", (now-startTime), " too short time to check yet")
        return
    sleepTime = systemSettings.get(u'batteryTest.run.time')
    drainLimit = systemSettings.get(u'batteryTest.run.drain')           
    timestamp = deviceDoc.get(u'systemTest.batteryTest.run.timestamp')      
    result = CheckBatteryLevel(deviceDoc, sleepTime, drainLimit, device, timestamp, client, db)
    if result:
        data = { u'systemTest.batteryTest.run.counter': firestore.Increment(1)}
        comFxn.UpdateFirebase(device.deviceId, data)    
        fxn.SetPassResult(client, device,"systemTest.batteryTest.run.timestamp", db)                    
    fxn.CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)