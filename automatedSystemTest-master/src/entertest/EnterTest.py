import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import os


def DeleteSystemTestColl(deviceId, db):
    try:
        coll = db.collection(u'devices' + '/' + deviceId + '/' + u'systemTest').stream()
        for doc in coll:
            doc.reference.delete()
    except Exception as err:
        print(err)

def AddUser(deviceId, user, db):
    user = user.replace('|', "QQQQ",1)  #to be able to upload to firebace, cloud function fix the rest
    try:
        userTimestamp = "users." +user + ".timestamp"
        userActive = "users."  + user + ".active"
        users = {
            userTimestamp : firestore.SERVER_TIMESTAMP,
            userActive : True
        }
        db.document(u'devices' + '/' + deviceId).update(users)
    except Exception as err:
       print(err)

def SetSubscription(deviceId, status, db):
    if status == "active":
        print("setting active sub: ",deviceId)
        data = {
            u'subscription.timestamp': firestore.SERVER_TIMESTAMP,
            u'subscription.status': "active", 
            u'subscription.isActive': True, 
        }    
    else:
        data = {
            u'subscription.timestamp': firestore.SERVER_TIMESTAMP,
            u'subscription.status': "inactive", 
            u'subscription.isActive': False, 
        }    
    doc = db.document(u'devices' + '/' + deviceId).update(data)


def DeleteFields(deviceId, config):
    data = {
        u'systemTest': firestore.DELETE_FIELD,
        u'users': firestore.DELETE_FIELD
    }    
    doc = config.db.document(u'devices' + '/' + deviceId).update(data)

def InsertDeviceIdInDevices(deviceArray, config):
    i=0
    for device in deviceArray:
        if device.startswith("3521191"):
            try:
                coll = config.db.collection(u'devices') \
                    .where(u'ids.imei', "==", device) \
                    .stream()
                for doc in coll:
                    print("putting ", doc.id, " instead of ", device)
                    deviceArray[i] = doc.id
                    i+=1
            except Exception as err:
                print(err)
                deviceArray[i] = ""
                i+=1

def SetUpDevices(config):
    #inserting device ids instead of imei
    print("Test devices: ")
    for deviceId in config.testDevices.values():    
        doc = config.db.document(u'devices' + '/' + deviceId).get()
        imei = doc.get(u'ids.imei')
        print(deviceId, " ", imei)

    print("\nWhich stage do you want to put it in?")
    i=1
    for stage in config.stages:
        print(str(i) + ")  "+stage)
        i+=1
    staging = input("\n")
    print("Stage is: " + config.stages[int(staging)-1])

    print("Entering config.testDevices.values")
    for deviceId in config.testDevices.values() :
        SetSubscription(deviceId, "active", config.db)        
        config.db.document(u'devices' + '/' + deviceId).update(data)



def SetServerSettings(config):
    try:
        config.db.document(u'systemTest'+'/'+u'settings').set(config.serverTestSettings)
    except Exception as err:
        print(err)
        print("problem setting test server settings")

