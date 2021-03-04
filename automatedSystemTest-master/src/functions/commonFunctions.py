from ..config import mainConfig as mainConfig

def Debug(module, *argv):
    if mainConfig.debugEnabled == True:
        print("[Debug ",module," ]", end=':')
        for arg in argv:
            print(arg)


def UpdateFirebase(deviceId, data):
    path = u'devices'+ '/' + deviceId
    try:
        mainConfig.db.document(path).update(data)
    except Exception as err:
        mainConfig.db.document(path).set(data, merge=True)
        print(err)
        print(deviceId, data)
