
from firebase_admin import firestore
import datetime, time, pytz
import random

from . import analyzerClasses as cls
from ..functions import commonFunctions as comFxn
from . import batteryModule as batteryMod

timezone=pytz.timezone('Europe/London')

## @package analyzerFunctions

## comFxn.Debug function for turning on and off debug print


## Connection function for MQTTT handling, called on connection success to mqtt server 
def onConnect(client, userdata, flags, rc):
    comFxn.Debug("Analyzer", "Connected analyzer to mqtt with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("$SYS/#")   

## Callback for handling events on the MQTT channels
def onMessage(client, userdata, msg):
    try:
        if msg.topic == "Scanner/device":
            data = msg.payload.decode("utf-8").split()
            device = cls.Device()
            device.deviceId = data[0]
            device.bleAddr = data[2]
            device.rssi = data[4]
            device.battery  = data[6]
            device.eventLoop = data[8]
            cls.analyzerQ.put(msg.topic)    
            cls.analyzerQ.put(device)
        if msg.topic == "Scanner/status":
            cls.analyzerQ.put(msg.topic)
            log = cls.StatusLog()
            cmd = msg.payload.decode("utf-8").split()
            log.reason = cmd[3:]
            log.status = cmd[2]
            log.bleAddr = cmd[1]
            log.event = cmd[0]
            cls.analyzerQ.put(log)
        if msg.topic == "bleControl/test":
            comFxn.Debug("Analyzer", "found it!!!!")
    except Exception as err:
        print(err)

## Function to update the Mode in firebase, this is to set the device in correct mde so testing
# can be handled in a correct way. This could be to ensure that a device is sleeping properly while doing wakeup events.
def DebugModeFireBase(deviceDoc, device, lightSleepDuration, deepSleepDuration, 
    stayAwakeDuration, enableSkipGps, tsLoc, accelInterrupt, usbInterrupt, db):
    comFxn.Debug("Analyzer", "DebugModeFireBase()")   
    data = {
            u'config.debugValues' : {
                "lightSleepDuration": lightSleepDuration,
                "deepSleepDuration" : deepSleepDuration,
                "stayAwakeDuration" : stayAwakeDuration,
                "enableSkipGpsSearch" : enableSkipGps,
                "enableLightSleepUsbInterrupt" : accelInterrupt,
                "enableDeepSleepUsbInterrupt" : accelInterrupt,
                "enableStayAwakeUsbInterrupt" : accelInterrupt,
                "enableLightSleepAccel" : usbInterrupt,
                "enableDeepSleepAccel" : usbInterrupt,
                "enableStayAwakeAccel" : usbInterrupt,
                "enableDebugSounds": True,
            },
            tsLoc : firestore.SERVER_TIMESTAMP
        }
    comFxn.UpdateFirebase(device.deviceId, data)

## checks the difference in time between positions, used to verify sleep modes.
def CheckPositionDiffTime(timediff, limit, systemSettings):
    comFxn.Debug("Analyzer", "CheckPositionDiffTime()")   
    diffAcceptance = systemSettings.get(u'sleepTest.communicationDiffAcceptance')
    comFxn.Debug("Analyzer", "Diff is: ", timediff," against limit ",limit)
    if timediff<0:
        return False
    if timediff > (limit-diffAcceptance) and timediff < (limit+diffAcceptance):
        comFxn.Debug("Analyzer", "position diff ok",timediff)
        return True
    return False

##  Counting number of docs in an array
def CountDocs(docs):
    i = 0
    for doc in docs:
        i+=1
    return i

## Checking the sleep cycle of one device, this is used to verify that the sleep has been of correct length
def CheckSleepCycle(deviceDoc, device, systemSettings, db):
    comFxn.Debug("Analyzer", "CheckSleepCycle()")   
    timeLimit = GetTimeLimit(deviceDoc, device)
    eventTimestamp = GetEventTimeStamp(deviceDoc, device)
    if eventTimestamp == 0:
        comFxn.Debug("Analyzer", "No eventtimestamp returning false")
        return 
    docs = db.document(u'devices' + '/' + device.deviceId).collection(u'data') \
        .order_by(u'timestamp', direction=firestore.Query.DESCENDING) \
        .where(u'timestamp', ">", eventTimestamp) \
        .limit(3) \
        .stream() 
    i=0
    myDocs = []
    for doc in docs:
        myDocs.append(doc)
    posTimeStamp = 0
    lastPosTimestamp = 0
    for doc in myDocs:
        #find INI
        comFxn.Debug("analyzer", "doc ...")
        postype = doc.get(u'type')
        ts = doc.get(u'timestamp') 
        posTimeStamp = time.mktime(ts.timetuple())       
        if CheckPositionDiffTime(abs(posTimeStamp-lastPosTimestamp), timeLimit, systemSettings):
            return True
        lastPosTimestamp = time.mktime(ts.timetuple())
    return False

## This is setting a test passed in firebase under the device in question. 
def SetPassResult(client, device, tsLoc,db):
    data = None
    comFxn.Debug("Analyzer", "SetPassResult()")   
    statusLog = cls.StatusLog()
    statusLog.SetLog(device.currentStage, "PASS" , device.bleAddr)
    #send log to server
    msg = "Setting pass in systemTest " + device.bleAddr
    client.publish("Analyzer/log", msg)
    db.collection(u'devices' + '/' + device.deviceId+'/'+'systemTest').add(statusLog.to_dict())
    client.publish("Analyzer/log", "Setting new event timestamp")
    try:
        data = { tsLoc : firestore.SERVER_TIMESTAMP }
        comFxn.UpdateFirebase(device.deviceId, data)
    except:
        db.document(u'devices' + '/' + device.deviceId).set(data)   


## This function deletes the whole log of systemtests under the device in firebase
def DeleteSystemTestCollection(deviceDoc, device, db):
    docs = db.document(u'devices' + '/' + device.deviceId + '/' + u'systemTest').stream()  ##only for testing TODO
    for doc in docs:
        comFxn.Debug("Analyzer", "deleting doc...")
        doc.reference.delete()

## Setting the new stage for the device
# @param deviceDoc: The device document gotten from firebase
# @param device object to be used, this contains the stages to be set already
# @param client: mqtt client object for logging
def NewStage(deviceDoc, device, client, db):
    comFxn.Debug("Analyzer", "NewStage()")
    HandleNextStage(deviceDoc, device, client, db)
    msg = "New stage for " + device.deviceId + " " + device.nextStage
    data = {u'systemTest.stage': device.nextStage}
    comFxn.UpdateFirebase(device.deviceId, data)  
    client.publish("Analyzer/log", msg)

## Checking if the number of events happened is compared to the limit for events in testsettings in firebase
def CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db):
    comFxn.Debug("Analyzer", "CheckEventLimit()")
    msg = "CheckEventLimit " + str(device.currentStage) + " " + str(device.deviceId) + " bleAddr: " + str(device.bleAddr) \
    + " Events: " + str(eventCounter) + " Limit: " + str(eventLimit)
    client.publish("Analyzer/log", msg)
    if(eventCounter >= eventLimit):
        #newStage if limit is reached
        NewStage(deviceDoc, device, client, db)
    return



#
def SetNewEncryptionKey(device, db):
    key = []
    for x in range(16):
        key.append(random.randint(0,255))
    comFxn.Debug("Analyzer", "Setting Key: ", key)
    try:
        data = {u'keys.encryption2' : key }
        db.document(u'deviceSecrets' +'/' + device.deviceId).update(data)
        data = {u'systemTest.encryption.key.timestamp' : firestore.SERVER_TIMESTAMP }
        comFxn.UpdateFirebase(device.deviceId, data)
    except Exception as err:
        data = {u'keys' :{u'encryption2' : key} }
        db.document(u'deviceSecrets' +'/' + device.deviceId).set(data, merge=True)
        data = {u'systemTest':{u'encryption': {u'key':{u'timestamp' : firestore.SERVER_TIMESTAMP }}}}
        db.document(u'devices' +'/' + device.deviceId).set(data, merge=True)
        comFxn.Debug("Analyzer", err)

## Handles the next stage for the device, when the device is going into a new stage, new settings need to be input 
# with regards to mode, sleeptime, accelererometer setup and so on2
# @param deviceDoc: device document stored from firebase
# @param device: device object to be used
# @param client: mqtt client object for logging
def HandleNextStage(deviceDoc, device, client, db):
    comFxn.Debug("Analyzer", "HandleNextStage()", device.nextStage)
    toSave = device.currentStage.replace("/",".")
    toSave = toSave.replace("bleControl","systemTest")  
    data = {
        toSave: u'PASS'
    }
    comFxn.UpdateFirebase(device.deviceId, data)
    bleAddr = deviceDoc.get(u'ids.bleAddress') 
    if device.nextStage == "bleControl/reset":
        data = {u'systemTest.bleTest.readyForAction':True, 
                u'systemTest.bleTest.reset.counter' : 0,}
        comFxn.UpdateFirebase(device.deviceId, data)
        DebugModeFireBase(deviceDoc, device, 0, 0, 60, True, "systemTest.startTimestamp", False, False, db)
        msg = device.bleAddr + " " + device.deviceId
        client.publish("bleControl/reset", msg)
        

    if device.nextStage == "bleControl/wakeup":
        data = {u'systemTest.bleTest.readyForAction':True, 
                u'systemTest.bleTest.wakeup.counter' : 0
                }
        comFxn.UpdateFirebase(device.deviceId, data)
        DebugModeFireBase(deviceDoc, device, 0, 255, 0, True, "systemTest.bleTest.wakeup.timestamp", False, False, db)
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)

    if device.nextStage == "systemTest/lightSleepRun": 
        data = {u'systemTest.sleepTest.lightSleep.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)
        DebugModeFireBase(deviceDoc, device, 6, 0, 0, False, "systemTest.sleepTest.lightSleep.timestamp", False, False, db) #TODO, set longer sleep time 
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)

    if device.nextStage == "systemTest/deepSleepRun": 
        data = {u'systemTest.sleepTest.deepSleep.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)    
        DebugModeFireBase(deviceDoc, device, 0, 1, 0, False, "systemTest.sleepTest.deepSleep.timestamp", False, False, db)   #TODO, set longer sleep time
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)

    if device.nextStage == "systemTest/stayAwakeRun":
        data = {u'systemTest.sleepTest.stayAwake.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)   
        DebugModeFireBase(deviceDoc, device, 0, 0, 6, False, "systemTest.sleepTest.stayAwake.timestamp", False, False, db)  #TODO, set longer sleep time
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)

    if device.nextStage == "systemTest/batteryTestRun": 
        data = {u'systemTest.batteryTest.run.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)
        settings = db.document(u'systemTest' + '/' + u'settings').get()
        sleep = settings.get(u'batteryTest.run.time')/10 
        DebugModeFireBase(deviceDoc, device, 0, 0, 6, False, "systemTest.batteryTest.run.timestamp", False, False, db)  #TODO, set longer sleep time
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)

    if device.nextStage == "systemTest/batteryTestSleep":
        data = {u'systemTest.batterytest.sleep.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)
        settings = db.document(u'systemTest' + '/' + u'settings').get()
        sleep = settings.get(u'batteryTest.sleep.time')
        DebugModeFireBase(deviceDoc, device, 0, sleep, 0, False, "systemTest.batteryTest.sleep.timestamp", False, False, db)  #TODO, set longer sleep time
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)

    if device.nextStage == "systemTest/batteryShutdown":
        data = {u'systemTest.batterytest.shutdown.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)
        settings = db.document(u'systemTest' + '/' + u'settings').get()
        sleep = settings.get(u'batteryTest.shutdown.time')
        DebugModeFireBase(deviceDoc, device, 0, 0, sleep, False, "systemTest.batteryTest.shutdown.timestamp", False, False, db)  #TODO, set longer sleep time
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)

    if device.nextStage == "accelerometerTest/lightSleepAccelerometerTest":  
        data = {u'systemTest.accelerometerTest.lightSleep.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data) 
        DebugModeFireBase(deviceDoc, device, 100, 0, 0, False, "systemTest.accelerometerTest.lightSleep.timestamp", True, False, db) 
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)
        
    
    if device.nextStage == "accelerometerTest/deepSleepAccelerometerTest":
        data = {u'systemTest.accelerometerTest.deepSleep.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)
        DebugModeFireBase(deviceDoc, device, 100, 0, 0, False, "systemTest.accelerometerTest.deepSleep.timestamp", True, False, db) 
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)
        
    
    if device.nextStage == "accelerometerTest/stayAwakeAccelerometerTest":
        data = {u'systemTest.accelerometerTest.stayAwake.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)
        DebugModeFireBase(deviceDoc, device, 0, 10, 100, False, "systemTest.accelerometerTest.stayAwake.timestamp", True, False, db)
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg) 
    
    if device.nextStage == "systemTest/encryptionKey":
        data = {u'systemTest.encryption.key.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)
        SetNewEncryptionKey(device,db)
        DebugModeFireBase(deviceDoc, device, 0, 0, 1, False, "systemTest.encryption.key.timestamp", False, False, db)
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)
        
    if device.nextStage == "systemTest/encryptionKeyReset":
        data = {u'systemTest.encryption.keyReset.counter' : 0}
        comFxn.UpdateFirebase(device.deviceId, data)
        SetNewEncryptionKey(device,db)
        DebugModeFireBase(deviceDoc, device, 0, 0, 1, False, "systemTest.encryption.keyReset.timestamp", False, False, db)
        msg = device.bleAddr + " " + device.deviceId
        client.publish("Manual/reset", msg)

    if device.nextStage == "systemTest/completed":
        pass    
    
    return device.nextStage


## Checking if the last position was a reset, this is to verify reset events happening on device
# @param device: device object to be used
# @param timestamp: time of the resetevent that has been run, this is to avoid using old events for verification
def CheckForResetBit(device,deviceDoc, timestamp, db):
    comFxn.Debug("Analyzer", "CheckForResetBit()")
    isReset = deviceDoc.get('latestData.isReset')  
    checkTs = deviceDoc.get("latestData.battery.timestamp") 
    comFxn.Debug("Analyzer", device.deviceId, isReset)
    print(device.deviceId, "ts:" ,timestamp.hour, timestamp.minute, "  checkts:", checkTs.hour, checkTs.minute)
    if checkTs > timestamp and isReset == True:
            return True      
    comFxn.Debug("Analyzer", "found no Resets in latestData" )
    return False

## Gets the correct sleep time for the event in question, this is used for comparison with the actual sleep time
# @param deviceDoc: device data gotten from firebase
# @param device: device object
def GetTimeLimit(deviceDoc, device):
    comFxn.Debug("Analyzer", "GetTimeLimit()")   
    limit = 0
    if device.currentStage == "systemTest/lightSleepRun":
        return deviceDoc.get(u'config.debugValues.lightSleepDuration')*10
    if device.currentStage == "systemTest/deepSleepRun":
        return deviceDoc.get(u'config.debugValues.deepSleepDuration')*60
    if device.currentStage == "systemTest/stayAwakeRun":
        return deviceDoc.get(u'config.debugValues.stayAwakeDuration')*10
    return 0

## Getting the timestamp of the last event of this type
# @param deviceDoc: device data gotten from firebase
# @param device: device object
def GetEventTimeStamp(deviceDoc, device):
    if device.currentStage == "systemTest/lightSleepRun":
        return deviceDoc.get(u'systemTest.sleepTest.lightSleep.timestamp')
    if device.currentStage == "systemTest/deepSleepRun":
        return deviceDoc.get(u'systemTest.sleepTest.deepSleep.timestamp')
    if device.currentStage == "systemTest/stayAwakeRun":
        return deviceDoc.get(u'systemTest.sleepTest.stayAwake.timestamp')
    return 0

## Used to verify encryption key, this function checks that we have comminucation in firebase from the device.
# Wrong encryptionkey will not go through to the server
# @param deviceDoc: device data gotten from firebase
# @param device: device object
# @param timestamp: timestamp of last key change event 
def CheckNewMessageAfterKeySet(deviceDoc, device, timestamp,db):
    coll = db.collection(u'devices' + '/' + device.deviceId + '/' + u'data') \
        .where(u'timestamp', ">", timestamp) \
        .limit() \
        .get()
    myDocs = []
    for doc in coll:
        myDocs.append(doc)
    if CountDocs(myDocs) > 1:  #at least two messages to ensure encryption has been set
        return True
    return False

## Checking if last wakeup was because of movement, this is used to verify accelerometer function.
# @param device: device object
# @param timestamp: timestamp of last movement event
def CheckForMovementBit(device, timestamp, db):
    coll = db.collection(u'devices' + '/' + device.deviceId + '/' + u'data') \
        .where(u'timestamp', ">", timestamp) \
        .where(u'type', "==", "INI") \
        .where(u'isMovementDetected', "==", True) \
        .limit(50) \
        .get()
    myDocs = []
    for doc in coll:
        myDocs.append(doc)
    if CountDocs(myDocs) > 0:  #at least two messages to ensure encryption has been set
        return True
    return False


## Checking that the intervas between bluetooth advertising is correct, if this is higher than the timelimit in 
# firebase, the test will fail
# @param device: device object
# @param systemSettings: test settings set in firebase
def CheckBluetoothIntervals(device, deviceDoc, systemSettings, db):
    comFxn.Debug("Analyzer", "CheckBluetoothIntervals", device.deviceId)
    maxDiff = None
    data = {u'systemTest.bleTest.intervals.latestTimestamp': firestore.SERVER_TIMESTAMP}
    comFxn.UpdateFirebase(device.deviceId, data)
    nowTimestamp = deviceDoc.get(u'systemTest.bleTest.intervals.latestTimestamp')
    try:
        lastTimestamp = deviceDoc.get(u'systemTest.bleTest.intervals.lastTimestamp')
    except Exception as err:
        comFxn.Debug("Analyzer", err)
        data = {u'systemTest.bleTest.intervals.lastTimestamp': firestore.SERVER_TIMESTAMP}
        comFxn.UpdateFirebase(device.deviceId, data)
        return
    diff = time.mktime(nowTimestamp.timetuple()) - time.mktime(lastTimestamp.timetuple())
    try:
        maxDiff = deviceDoc.get(u'systemTest.bleTest.intervals.maxDiff')
    except Exception as err:
        comFxn.Debug("Analyzer", err)
        comFxn.Debug("Analyzer", "setting Maxdiff var")
        data = {u'systemTest.bleTest.intervals.maxDiff': 0}
        comFxn.UpdateFirebase(device.deviceId, data)
    if diff > maxDiff:
        data = {u'systemTest.bleTest.intervals.maxDiff': diff}
        comFxn.UpdateFirebase(device.deviceId, data)
        if diff > systemSettings.get(u'bleTest.intervals.timeLimit'):
            data = {u'systemTest.bleTest.intervals.result': "FAIL"}
            comFxn.UpdateFirebase(device.deviceId, data)
    data = {u'systemTest.bleTest.intervals.lastTimestamp': nowTimestamp}
    comFxn.UpdateFirebase(device.deviceId, data)

## Checking the current stage of the device. And handling this into the correct course of action.
# @param deviceDoc: device data gotten from firebase
# @param client: mqtt client object
# @param deviceDoc: device data gotten from firebase
# @param systemSettings: test settings from firebase 
def CheckStage(deviceDoc, client, device, systemSettings, db):
    try:
        comFxn.Debug("Analyzer", "CheckStage()")   
        msg = "Checking " + str(device.currentStage) + " " + device.deviceId
        client.publish("Analyzer/log", msg)
        eventCounter = 0
        #checking bluetooth intervals
        CheckBluetoothIntervals(device, deviceDoc,  systemSettings, db)
        #looking for events of this type
        try:
            docs = db.document(u'devices' + '/' + device.deviceId).collection(u'systemTest') \
                .where(u'event', "==", device.currentStage) \
                .stream()
            for doc in docs:
                eventCounter +=1
        except:
            comFxn.Debug("Analyzer", "no events Found yet") 
        #setting bluetoothTestResults
        client.publish("Analyzer/log", "Events Found " + str(eventCounter) )
        #getting limit
        rssiLimit = systemSettings.get(u'bleTest.rssi.limit')
        rssiMax = 0
        try:
            rssiMax = deviceDoc.get(u'systemTest.bleTest.rssiMax')
        except:
            pass
        #setting result, setting ok if good
        if int(device.rssi) > int(rssiMax) or rssiMax == 0:
            data = { u'systemTest.bleTest.rssiMax' : device.rssi}
            comFxn.UpdateFirebase(device.deviceId, data)
        if int(device.rssi) > rssiLimit:
            data = { u'systemTest.bleTest.rssiTest': "PASS" }
            comFxn.UpdateFirebase(device.deviceId, data)
        print(device.currentStage)  
        if device.currentStage == "systemTest/start":
            CheckEventLimit(deviceDoc, 0, 1, device, client, db)
            return 

        if device.currentStage == "bleControl/reset":
            #check how many events are done, compare to limit
            eventLimit = systemSettings.get(u'bleTest.reset.limit')
            ts = GetTimestamp(u'systemTest.bleTest.reset.timestamp', device, deviceDoc, db)
            if CheckForResetBit(device, deviceDoc, ts, db):            
                data = { u'systemTest.bleTest.reset.counter': firestore.Increment(1),            
                        u'systemTest.bleTest.readyForAction':True,}
                comFxn.UpdateFirebase(device.deviceId, data)
            SetResetRetry(device, deviceDoc, ts)
            CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            return
            
        if device.currentStage == "bleControl/factoryReset":
            pass
            #check how many events are done, compare to limit
            eventLimit = systemSettings.get(u'bleTest.factoryReset.limit')  
            #TODO: check resethappeningbit
            #time since event
            eventTime = deviceDoc.get(u'systemTest.bleTest.factoryReset.timeStamp')
            waitTime = systemSettings.get(u'bleTest.factoryReset.waitTime')
            data = {u'systemTest.checkInTime': firestore.SERVER_TIMESTAMP}
            comFxn.UpdateFirebase(device.deviceId, data)
            now = deviceDoc.get(u'systemTest.checkInTime')   
            now = time.mktime(now.timetuple())
            #TODO: check that time has not run out, if not run out, set new Factory reset timestamp   
            ts = GetTimestamp(u'systemTest.bleTest.factoryReset.timestamp', device, deviceDoc, db) 
            if (now - eventTime) > waitTime and CheckForResetBit(device, deviceDoc, ts, db) == True:           
                data = { u'systemTest.bleTest.factoryReset.timestamp': firestore.SERVER_TIMESTAMP, 
                    u'systemTest.bleTest.factoryReset.counter': firestore.Increment(1)}
                comFxn.UpdateFirebase(device.deviceId, data)
            CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            return 
            #set Timer for poweron
        
        if device.currentStage == "bleControl/wakeup":
            comFxn.Debug("Analyzer", "Checking Wakeup Stage")
            #check how many events are done, compare to limit
            eventLimit = systemSettings.get(u'bleTest.wakeup.limit')
            ts = GetTimestamp(u'systemTest.bleTest.wakeup.timestamp', device, deviceDoc, db) 
            if CheckForResetBit(device,deviceDoc, ts, db) == False:           
                data = { u'systemTest.bleTest.wakeup.timestamp': firestore.SERVER_TIMESTAMP, 
                    u'systemTest.bleTest.wakeup.counter': firestore.Increment(1) }
                comFxn.UpdateFirebase(device.deviceId, data)
            CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            return
        
        if device.currentStage == "systemTest/lightSleepRun":
            eventLimit = systemSettings.get(u'sleepTest.lightSleep.limit')
            if CheckSleepCycle(deviceDoc, device, systemSettings, db): 
                SetPassResult(client, device, "systemTest.sleepTest.lightSleep.timestamp", db)                     
                data = { u'systemTest.sleepTest.lightSleep.counter': firestore.Increment(1)}
                comFxn.UpdateFirebase(device.deviceId, data)        
            CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            return
            #check 
        
        if device.currentStage == "systemTest/deepSleepRun":
            eventLimit = systemSettings.get(u'sleepTest.deepSleep.limit')
            if CheckSleepCycle(deviceDoc, device, systemSettings,db): 
                SetPassResult(client, device, "systemTest.sleepTest.deepSleep.timestamp", db)   
                data = { u'systemTest.sleepTest.deepSleep.counter': firestore.Increment(1)}
                comFxn.UpdateFirebase(device.deviceId, data)     
            CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            return
            #get two last positions
            #get timestamps, check time
            #check battery drainage betwee
            #check 
        
        if device.currentStage == "systemTest/stayAwakeRun":
            eventLimit = systemSettings.get(u'sleepTest.stayAwake.limit')
            if CheckSleepCycle(deviceDoc, device, systemSettings,db): 
                SetPassResult(client, device,"systemTest.sleepTest.stayAwake.timestamp", db)    
                data = { u'systemTest.sleepTest.stayAwake.counter': firestore.Increment(1)}
                comFxn.UpdateFirebase(device.deviceId, data)    
            CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            return
        
        if device.currentStage == "systemTest/batteryTestRun":   
            batteryMod.BatteryTestRun(deviceDoc, device, db, systemSettings, client, eventCounter)
            return

        if device.currentStage == "systemTest/batteryTestSleep":
            batteryMod.BatteryTestSleep(deviceDoc, db, systemSettings, eventCounter,device,client )
            return
        
        if device.currentStage == "systemTest/batteryShutdown":
            batteryMod.BatteryShutdown(device, deviceDoc, systemSettings, db, client)
            return

        if device.currentStage == "accelerometerTest/lightSleepAccelerometerTest":
            eventLimit = systemSettings.get(u'sleepTest.lightSleepAccelerometerTest.limit')
            # Check sleepingBit
            if device.eventLoop != "lightSleep":
                return
            #check for movement bit since timestamp           
            timestamp = deviceDoc.get(u'systemTest.accelerometerTest.lightSleep.timestamp')      
            if CheckForMovementBit(device, timestamp, db):             
                #if found pass test
                data = { u'systemTest.accelerometerTest.lightSleep.counter': firestore.Increment(1)}
                comFxn.UpdateFirebase(device.deviceId, data)  
                SetPassResult(client, device,"systemTest.accelerometerTest.lightSleep.timestamp", db)
                CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            client.publish("Manual/movement", "activate")
            #if not Activate movement
            return

        if device.currentStage == "accelerometerTest/deepSleepAccelerometerTest":
            eventLimit = systemSettings.get(u'sleepTest.deepSleepAccelerometerTest.limit')
            # Check sleepingBit
            if device.eventLoop != "deepSleep":
                return
            #check for movement bit since timestamp           
            timestamp = deviceDoc.get(u'systemTest.accelerometerTest.deepSleep.timestamp')      
            if CheckForMovementBit(device, timestamp, db):             
                #if found pass test
                data = { u'systemTest.accelerometerTest.deepSleep.counter': firestore.Increment(1)}
                comFxn.UpdateFirebase(device.deviceId, data)  
                SetPassResult(client, device,"systemTest.accelerometerTest.deepSleep.timestamp", db)
                CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            client.publish("Manual/movement", "activate")
            return

        if device.currentStage == "accelerometerTest/stayAwakeAccelerometerTest":
            eventLimit = systemSettings.get(u'sleepTest.stayAwakeAccelerometerTest.limit')
            # Check sleepingBit
            if device.eventLoop != "stayAwake":
                return
            #check for movement bit since timestamp           
            timestamp = deviceDoc.get(u'systemTest.accelerometerTest.stayAwake.timestamp')      
            if CheckForMovementBit(device, timestamp, db):             
                #if found pass test
                data = { u'systemTest.accelerometerTest.stayAwake.counter': firestore.Increment(1)}
                comFxn.UpdateFirebase(device.deviceId, data)  
                SetPassResult(client, device,"systemTest.accelerometerTest.stayAwake.timestamp", db)
                CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            client.publish("Manual/movement", "activate")
            return

        if device.currentStage == "systemTest/encryptionKey":
            eventLimit = systemSettings.get(u'encryption.key.limit')
            CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            try:
                doc = db.document(u'deviceSecrets' +'/' + device.deviceId).get()
                doc.get(u'keys.encryption2')
            except:
                comFxn.Debug("Analyzer", "No key2 set")           
                timestamp = deviceDoc.get(u'systemTest.encryption.key.timestamp')  
                if CheckNewMessageAfterKeySet(deviceDoc, device, timestamp,db):
                    SetPassResult(client, device,"systemTest.encryption.key.timestamp", db)
                    SetNewEncryptionKey(device,db)
                    CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            return

        if device.currentStage == "systemTest/encryptionKeyReset":
            eventLimit = systemSettings.get(u'encryption.keyReset.limit')
            CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)

            try:
                doc = db.document(u'deviceSecrets' +'/' + device.deviceId).get(u'keys.encryption2')
                doc.get(u'keys.encryption2')
            except:
                comFxn.Debug("Analyzer", "No key2 set")           
                timestamp = deviceDoc.get(u'systemTest.encryption.keyReset.timestamp')  
                if CheckNewMessageAfterKeySet(deviceDoc, device, timestamp,db) and CheckForResetBit(device,deviceDoc, timestamp, db):
                    SetPassResult(client, device,"systemTest.encryption.keyReset.timestamp", db)
                    SetNewEncryptionKey(device,db)
                    CheckEventLimit(deviceDoc, eventLimit, eventCounter, device, client, db)
                    
                    client.publish("Manual/reset", device.bleAddr, device.deviceId)
            return
        
        if device.currentStage == "systemTest/completed":
            pass
            #do nothing

        comFxn.Debug("Analyzer", "No registered events yet: testing continue   ", device.currentStage, device.deviceId)
    except Exception as err:
        print(err)

def GetTimestamp(tsLoc, device, deviceDoc, db):    
    try: 
        ts = deviceDoc.get(tsLoc)
        return ts
    except:
        data = {
            tsLoc: firestore.SERVER_TIMESTAMP,
            "systemTest.bleTest.readyForAction": True
        }
        db.document('devices'+'/'+device.deviceId).update(data)
        ts = deviceDoc.get(tsLoc)
        return ts

def SetResetRetry(device, deviceDoc, ts):
    if isTimestampOld(deviceDoc, ts, minuteLimit=10):
        comFxn.Debug("Analyzer", device.deviceId, " old timestamp, setting new readyforaction")
        if device.currentStage == "bleControl/reset":
            data = {"systemTest.bleTest.readyForAction": True,
                    "systemTest.bleTest.reset.oldTimestamp": firestore.Increment(1)}
            comFxn.UpdateFirebase(device.deviceId, data)

def isTimestampOld(deviceDoc, ts, minuteLimit):
    latest = deviceDoc.get('battery.timestamp')
    if latest - ts > datetime.timedelta(minutes=minuteLimit):
        return True
    return False



