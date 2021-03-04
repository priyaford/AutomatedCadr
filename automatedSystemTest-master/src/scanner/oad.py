from bluepy import btle
from bluepy.btle import Scanner, DefaultDelegate, Peripheral
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import requests
from multiprocessing import Queue
import time
import math
from . import scannerFunctions as fxn
from . import scannerClasses as cls
from ..functions import commonFunctions as comFxn

##Bluetooth HW setup
#sudo nano /sys/kernel/debug/bluetooth/hci0/conn_min_interval 
#sudo nano /sys/kernel/debug/bluetooth/hci0/conn_max_interval

## Oad Process:
# Open peripheral connection
# Update connection interval for faster oad
# enable OAD image identify notifications
# enable notifications on Image block characteristic
# Write header to Image identify characteristic
#       Image is verified by checking Image header, BIM- and metadata- versions, and length of image
#       Boundary checks are done on app or stack image
#       Target will switch to configuration state, it will get the block size and set image count
# Send start OAD command
#       Target will respond with request for first block
# Send first block
#       Target will respond with request for next block
# etc...
#       CRC is caclulated on target
#       Image will be copied to flash if enableOad command is set
# Errors: any errors gotten will require the OAD downloader to restart the OAD transfer from the beginning


oadQueue = Queue()

class Characteristic(object):
    def __init__(self, uuid, char, handle):
        self.uuid = uuid
        self.char = char
        self.handle = handle
        self.cccdHandle = handle+1


class OadCharacteristics(object):
    def __init__(self):
        pass
    def AddImageIdentify(self, uuid, char, handle):
        self.imageIdentify = Characteristic(uuid, char, handle)
    def AddImageBlock(self,uuid,char, handle):
        self.imageBlock = Characteristic(uuid, char, handle)
    def AddOadControl(self,uuid,char, handle):
        self.oadControl = Characteristic(uuid, char, handle)
    def AddBlePin(self,uuid,char, handle):
        self.blePin = Characteristic(uuid, char, handle)
    def AddCommands(self,uuid,char, handle):
        self.commands = Characteristic(uuid, char, handle)
    def AddDeviceData(self,uuid,char, handle):
        print("found This")
        self.deviceData = Characteristic(uuid, char, handle)


class OadImageContainer(object):
    def __init__(self,header,image):
        self.header = header
        self.data = image
        self.imageBlock = []
    
    def MakeBlocks(self,blockSize):
        self.blockSize = blockSize
        imageStart = int.from_bytes(self.header.imgHeaderLength,"big")
        #self.data = self.data[imageStart:]
        blockSize = blockSize-4 #removing placement for blocknumber
        self.noOfBlocks = math.ceil(int(len(self.data)/blockSize))
        for i in range(0,self.noOfBlocks+1):
            beginning = [(i >> k & 0xff) for k in (0,8,16,24)]
            dataBlock = bytearray(beginning)
            start = i*blockSize
            stop = start+blockSize
            for byte in self.data[start:stop]:
                dataBlock.append(byte)
            dataBlock = bytearray(dataBlock)
            self.imageBlock.append(dataBlock)

class ContiguousInfo(object):
    def __init__(self, data):
        self.segmentType = data[0]             
        self.wirelessTech = data[1:3]
        self.rfu4 = data[3]
        self.payloadLength = data[4:8]
        self.imageStartAddr = data[8:12] #image start address

class BoundaryInfo(object):
    def __init__(self, data):
        self.segmentType = data[0]
        self.wirelessTech = data[1:3]
        self.rfu3 = data[3]
        self.payloadLength = data[4:8]
        self.stackStartAddr = data[8:12] #start addr of stack image
        self.ICALL_STACK0_ADDR = data[12:16] #stack start address
        self.RAM_START_ADDR = data[16:20] #ram entry
        self.RAM_END_ADDR = data[20:24] #ram end

class ImageInfo(object):
    def __init__(self,data):
        self.imgCopyStatus = data[0]
        self.crcStatus = data[1]
        self.imgType = data[2]
        self.imgNumber = data[3]

class OadImageHeader(object):
    def __init__(self, data):
        temp = []
        self.imgSwVersion = []
        self.oadImageIdentificationValue = data[0:8]
        self.CRC = data[8:12]
        self.bimVersion = data[12]
        self.imgHeaderVersion = data[13] #metadataversion
        self.wirelessTech = data[14:16]
        self.imgInfo = ImageInfo(data[16:20])
        self.imgValidation = data[20:24]
        self.imgLength = data[24:28]             #turn this around
        self.programEntryAddress = data[28:32]
        temp = data[32:36]
        for i in range(3,-1,-1):
            self.imgSwVersion.append(temp[i]) 
        self.imgEndAddress = data[36:40]
        self.imgHeaderLength = data[40:42]
        self.rfu2 = data[42:44]
        self.boundaryInfo = BoundaryInfo(data[44:68])
        #segtypeImg for contiguous image
        self.contiguousImgInfo = ContiguousInfo(data[68:80])
        self.imageIdentifyPayload = []
        self.CreateImageIdentifyPayload()
    def CreateImageIdentifyPayload(self):
        for byte in bytearray(self.oadImageIdentificationValue):
            self.imageIdentifyPayload.append(byte)
        self.imageIdentifyPayload.append(self.bimVersion)
        self.imageIdentifyPayload.append(self.imgHeaderVersion)
        self.imageIdentifyPayload.append(self.imgInfo.imgCopyStatus)
        self.imageIdentifyPayload.append(self.imgInfo.crcStatus)
        self.imageIdentifyPayload.append(self.imgInfo.imgType)
        self.imageIdentifyPayload.append(self.imgInfo.imgNumber)
        for byte in bytearray(self.imgLength):
            self.imageIdentifyPayload.append(byte)
        for byte in bytearray(self.imgSwVersion):
            self.imageIdentifyPayload.append(byte)
        self.imageIdentifyPayload = bytes(self.imageIdentifyPayload)

def Convert4Byte(numbers):
    number1 = int.from_bytes(numbers[0:2],"little")<<16
    number2 = int.from_bytes(numbers[2:4],"little")
    return hex(number1 | number2)

def Convert2Byte(numbers):
    number1 = int.from_bytes(numbers,"little")
    return hex(number1)

def MakeStuffUpLittleEndian(data):
    return hex(int.from_bytes(data, "little")),int.from_bytes(data, "little")
def MakeStuffUpBigEndian(data):
    return hex(int.from_bytes(data, "big")), int

def PrintHeader(header):    
    print("oadImageIdentificationValue: ",header.oadImageIdentificationValue)
    print("crc: ",MakeStuffUpLittleEndian(header.CRC))
    print("bimVersion:", header.bimVersion)
    print("imgHeaderVersion:", header.imgHeaderVersion)
    print("wirelessTech:", MakeStuffUpLittleEndian(header.wirelessTech))
    print("imgCopyStatus:", header.imgInfo.imgCopyStatus)
    print("crcStatus:", header.imgInfo.crcStatus)
    print("imgType:", header.imgInfo.imgType)
    print("imgNumber:", header.imgInfo.imgNumber)
    print("imgValidation:", header.imgValidation)
    print("imgLength:", MakeStuffUpLittleEndian(header.imgLength))
    print("programEntryAddress:", MakeStuffUpLittleEndian(header.programEntryAddress))
    print("imgSwVersion:", MakeStuffUpLittleEndian(header.imgSwVersion))
    print("imgEndAddress:", MakeStuffUpLittleEndian(header.imgEndAddress))
    print("imgHeaderLength:", MakeStuffUpLittleEndian(header.imgHeaderLength))
    print("boundaryInfo.segmentType:", header.boundaryInfo.segmentType)
    print("boundaryInfo.wirelessTech:", header.boundaryInfo.wirelessTech)
    print("boundaryInfo.payloadLength:", MakeStuffUpLittleEndian(header.boundaryInfo.payloadLength))
    print("boundaryInfo.stackStartAddr:", MakeStuffUpLittleEndian(header.boundaryInfo.stackStartAddr))
    print("boundaryInfo.ICALL_STACK0_ADDR:", MakeStuffUpLittleEndian(header.boundaryInfo.ICALL_STACK0_ADDR))
    print("boundaryInfo.RAM_START_ADDR:", MakeStuffUpLittleEndian(header.boundaryInfo.RAM_START_ADDR))
    print("boundaryInfo.RAM_END_ADDR:", MakeStuffUpLittleEndian(header.boundaryInfo.RAM_END_ADDR))
    print("contiguousImgInfo.segmentType:", header.contiguousImgInfo.segmentType )
    print("contiguousImgInfo.wirelessTech:", MakeStuffUpLittleEndian(header.contiguousImgInfo.wirelessTech))
    print("contiguousImgInfo.payloadLength:", MakeStuffUpLittleEndian(header.contiguousImgInfo.payloadLength))
    print("contiguousImgInfo.imageStartAddr:", MakeStuffUpLittleEndian(header.contiguousImgInfo.imageStartAddr))

oadCharacteristicUuid = {
    "imageIdentifyChar" :   "f000ffc1-0451-4000-b000-000000000000",
    "imageBlockChar" :      "f000ffc2-0451-4000-b000-000000000000",
    "oadExtControlChar" :   "f000ffc5-0451-4000-b000-000000000000",
    "blePinChar" :          "3b941110-94a3-4b04-ab27-336173113a33",
    "commands" :            "3b941080-94a3-4b04-ab27-336173113a33",
    "deviceData" :          "3b941130-94a3-4b04-ab27-336173113a33"
}

oadCommand = {
    "enableNotification" : [b'0x01',b'0x00']
}

controlCharacteristic = {
    "command" : {
        "getOadBlockSize" : b'\x01', #get the active block size
        "setImageCount" : b'\x02',
        "startOadProcess" : b'\x03',
        "enableOadImage" : b'\x04',
        "cancelOad" : b'\x05',
        "disableOadImageBlockWrite": b'\x06',
        "getSoftwareVersion" : b'\x07',
        "getOadImageStatus" : b'\x08',
        "getProfileVersion" : b'\x09',
        "getDeviceType" : b'\x10',
        "eraseAllBonds" : b'\x13'
    },
    "response":{
        "getOadBlockSize" : [0,0,0],        #   OAD_BLOCK_SIZE
        "setImageCount" : [0,0],            #   byte0: command is(0x02), byte 1: Return status
        "startOadProcess" : b'\x03',    #   byte 0: command id: byte 1-3 Block number   
        "enableOadImage" : [0,0],           #   byte0: command is, byte 1: return status
        "cancelOad" : [0,0],                #   byte0: command id, byte 1 return status
        "disableOadImageBloclWrite": [0,0],  #   byte0: command id, byte 1 return status
        "getSoftwareVersion" : [0,0,0,0,0], #   byte0: command id, byte 1-4: current softwarre version
        "getOadImageStatus" : [0,0],        #   byte0: command id, byte 1 return status
        "getProfileVersion" : [0,0],        #   byte0: command id, byte 1: version of OAD profile supported
        "getDeviceType" : [0,0,0,0,0],      #   byte0: command id, byte 1-4: Value of deviceID register
        "ImageBlockWrite": [0,0,0,0,0,0],   #   byte0: command id, byte1: status of previous block, byte2-5: block number          
        "eraseAllBonds" : [0,0]             #   byte0: command id, byte 1 return status
    }
}

oadReturnValues = {
    0 :"OAD_SUCCESS",             #   OAD succeeded
    1 : "OAD_CRC_ERR",              #   The downloaded image’s CRC doesn’t match the one expected from the metadata
    2 : "OAD_FLASH_ERR",            #   Flash function failure such as flashOpen/flashRead/flash write/flash erase
    3 : "OAD_BUFFER_OFL",           #   The block number of the received packet doesn’t match the one requested, an overflow has occurred.
    4 : "OAD_ALREADY_STARTED",     #   OAD start command received, while OAD is already is progress
    5 : "OAD_NOT_STARTED",          #   OAD data block received with OAD start process
    6 : "OAD_DL_NOT_COMPLETE",      #   OAD enable command received without complete OAD image download
    7 : "OAD_NO_RESOURCES",         #   Memory allocation fails/ used only for backward compatibility
    8 : "OAD_IMAGE_TOO_BIG",        #   Image is too big
    9 : "OAD_INCOMPATIBLE_IMAGE",   #   Stack and flash boundary mismatch, program entry mismatch
    10 : "OAD_INVALID_FILE",        #	Invalid image ID received
    11 : "OAD_INCOMPATIBLE_FILE",   #	BIM/image header/firmware version mismatch
    12 : "OAD_AUTH_FAIL",           #	Start OAD process / Image Identify message/image payload authentication/validation fail
    13 : "OAD_EXT_NOT_SUPPORTED",   #	Data length extension or OAD control point characteristic not supported
    14 : "OAD_DL_COMPLETE",         #	OAD image payload download complete
    15 : "OAD_CCCD_NOT_ENABLED",    #	Internal (target side) error code used to halt the process if a CCCD has not been enabled
    16 : "OAD_IMG_ID_TIMEOUT"       #	OAD Image ID has been tried too many times and has timed out. Device will disconnect.
}

class MyDelegate(btle.DefaultDelegate):
    def __init__(self, characteristics, returnValues):
        btle.DefaultDelegate.__init__(self)
        self.characteristics = characteristics
        self.returnValues = returnValues
        # ... initialise here

    def handleNotification(self, cHandle, data):
        try:
            handleList = {
                self.characteristics.imageIdentify.handle : "imageIdentify",
                self.characteristics.oadControl.handle : "oadControl",
                self.characteristics.imageBlock.handle : "imageBlock",
                self.characteristics.deviceData.handle : "deviceData",
            }
            oadQueue.put(data)
        except Exception as err:
            print(err)
            raise cls.BluetoothError("Error Handling Response")

def GetOadImage(currentVersion, db):
    doc = db.document(u'firmwares'+'/'+currentVersion).get()
    url = doc.get(u'url')
    imageFile = requests.get(url)
    header = OadImageHeader(imageFile.content)
    #PrintHeader(header)
    image = imageFile.content
    #print("image len",  len(image))
    oadImage = OadImageContainer(header, image)
    i=1
    #for block in oadImage.imageBlock:
    #    print("block:" ,i,"\n", block)
    #    i+=1
    return oadImage

def VerifyImageHeader(oadImage):    
    if oadImage.header.imgInfo.imgType == 1: 
        return True
    raise cls.OadError("Header Verification Fault")

def ConnectToDevice(bleAddress, peripheral):
    try:
        print("made peripheral, connecting...")
        peripheral.connect(bleAddress)
        return True
    except:
        print("problem opening peripheral")  
    peripheral.disconnect()     
    return False


def HandleNotification(p, q, notifyTime, responseCode, singleResponse, error): 
    while not q.empty():
        temp = q.get() #emptying queue
    timeoutCounter = 0   
    while 1:
        if p.waitForNotifications(notifyTime):
            #handlenotification
            pass
        if not q.empty():
            response = q.get()
            print("Response: ", response)
            intResp = [x for x in response]
            hexResp = [hex(x) for x in response]
            #print("response in startOad ", intResp, hexResp)
            if singleResponse == True and intResp[0] == responseCode:
                    return intResp
            if intResp[0] == responseCode and intResp[1] == 0x00:
                return intResp
            print(intResp[11],"respcode:", responseCode)
            if intResp[11] == responseCode:
                print("found correct response")
                return intResp[11]
            print("Error: ", intResp[11], type(intResp[11]))
            raise cls.OadError(oadReturnValues[intResp[1]])             
        timeoutCounter +=1
        if timeoutCounter > 200:
            print(error, timeoutCounter)
            raise cls.OadError(error)

def SendStartOadCommand(chars, notifyTime, p, q):
    # Send start OAD command    
    print("\n-----Send Start oad Command-----")
    chars.oadControl.char.write(controlCharacteristic["command"]["startOadProcess"])
    #       Target will respond with request for first block, wait for this
    intResp = HandleNotification(p, q, notifyTime, 18, False,  "Start Oad timeout")
    blockNumber = intResp[1] or (intResp[2]<<8) or (intResp[3]<<16)                 

def WriteBlocks(image, chars, notifyTime, p, q):
    # Send blockNumber
    print("\n-----Writing Blocks-----")
    nextBlock = 0
    while 1:
        goToNextBlock = False
        print("Writing block ", nextBlock, " of ", image.noOfBlocks, "\r", end=" ")
        chars.imageBlock.char.write(image.imageBlock[nextBlock])
        timeoutCounter = 0
        while not goToNextBlock:
            if timeoutCounter == 50:     
                nextBlock+=1           
                print("trying next block ", nextBlock, " of ", image.noOfBlocks)
                chars.imageBlock.char.write(image.imageBlock[nextBlock])
            if p.waitForNotifications(notifyTime):
                #handlenotification
                pass
            if not q.empty():
                response = q.get()
                intResp = [x for x in response]
                if intResp[0] == 18 and intResp[1] == 0:
                    nextBlock = int.from_bytes([intResp[2],intResp[3]],'little')
                    goToNextBlock = True
                if intResp[0] == 18 and intResp[1] == 14:
                    print("\nDownload Complete")
                    return
                if intResp[0] == 18 and intResp[1] != 0:
                    print("Error in response")
                    if intResp[1] != 14:
                        error = "BlockWrite Error: "+ oadReturnValues[intResp[1]]
                        raise cls.OadError(error)
            timeoutCounter +=1
            if timeoutCounter > 100:
                print("response timeout", timeoutCounter)
                raise cls.OadError("BlockWrite Error: TIMEOUT")

def GetImageStatus(chars, notifyTime, p, q):
    chars.oadControl.char.write(bytes(controlCharacteristic["command"]["getOadImageStatus"]))
    intResp = HandleNotification(p, q, notifyTime, 8, True, "GetImageStatus timeout")
    if intResp[1] != 14:
        raise cls.OadError(oadReturnValues[intResp[1]])
    return

def ErasePreviousBonds(chars, notifyTime, p, q):    
    print("\n-----Erase Bonds-----")
    chars.oadControl.char.write(bytes(controlCharacteristic["command"]["eraseAllBonds"]))
    intResp = HandleNotification(p, q, notifyTime, 19, False, "EraseBonds timeout")


def GetOadImageStatus(chars, notifyTime, p,  q):    
    print("\n-----Get oad image status-----")
    chars.oadControl.char.write(bytes(controlCharacteristic["command"]["getOadImageStatus"]))
    intResp = HandleNotification(p, q, notifyTime, 8, True, "GetOadImageStatus error")

def EnableNotifications(chars, p):
    p.writeCharacteristic(chars.imageIdentify.cccdHandle, b'\x01\x00')
    # enable notifications on Image block characteristic
    p.writeCharacteristic(chars.imageBlock.cccdHandle, b'\x01\x00')
    # enable notifications on oad control point characteristic    
    p.writeCharacteristic(chars.oadControl.cccdHandle, b'\x01\x00')
    # enable notifications on deviceData characteristic    
    p.writeCharacteristic(chars.deviceData.cccdHandle, b'\x01\x00')

def GetBlockSize(chars, notifyTime, p, q):    
    print("\n-----get oad Block Size-----")
    chars.oadControl.char.write(bytes(controlCharacteristic["command"]["getOadBlockSize"]))
    #wait for notification from oadControl    
    intResp = HandleNotification(p, q, notifyTime, 0x01, True, "BlockSize Error")
    print("blockSize gotten: ", intResp[1])
    return intResp[1]

def WriteImageHeader(image, chars, notifyTime, p, q):
    # Write header to Image identify characteristic, only a portion of the header shall be sent(in order):
    # - OAD image identification value
    # - BIM version
    # - Image header Version
    # - Image information
    # - Image Length
    # - Software version
    #       Image is verified by checking Image header, BIM- and metadata- versions, and length of image
    #       Boundary checks are done on app or stack image
    #       Target will switch to configuration state, it will get the block size and set image count
    chars.imageIdentify.char.write(image.header.imageIdentifyPayload)
    intResp = HandleNotification(p, q, notifyTime, 0x00, True, "Image Identify Error")
    


def CheckCharacteristics(chars):
    try:
        test = chars.imageIdentify
        test = chars.imageBlock
        test = chars.oadControl
        test = chars.blePin
        test = chars.commands
        test = chars.deviceData
    except:
        raise cls.OadError("Not Found all Characteristics")

def GetCurrentFirmwareVersion(device, client, systemSettings):
    try:
        currentVersion = device.get(u'versions.tiFirmware')
        print("Current version is ", currentVersion)
        toVersion = systemSettings.get(u'oadTest.toFirmware')
        print("to version is ", toVersion)
        fromVersion = systemSettings.get(u'oadTest.fromFirmware')
        print("from version is ", fromVersion)
        if currentVersion == fromVersion:
            print("Updating with ", toVersion)
            msg = "Updating to " + str(toVersion) + " from " + str(fromVersion)
            client.publish("Scanner/log", msg)
            return toVersion
        if currentVersion == toVersion:
            print("Updating with ", fromVersion)
            msg = "Updating to " + str(fromVersion) + " from " + str(toVersion)
            client.publish("Scanner/log", msg)
            return fromVersion
        return toVersion
    except Exception as err:    
        print(err)
        raise cls.DatabaseError("Error Getting FirmwareVersions")


    

def doOad(bleAddress, deviceId, client, peripheral, config):
    systemSettings = config.db.document(u'systemTest'+u'/'+u'settings').get()
    device = config.db.document('devices'+'/'+deviceId).get()
    if device.get('battery.level') < 5:
        client.publish("Scanner/log", "Battery too low")
        return
    waitForNotificationTime = 0.1
    ## Oad Process:
    #scan for devices
    #testBleAddr = "80:6f:b0:c6:d6:a1"    #0597
    # get Oad numer to go to
    image = GetOadImage(GetCurrentFirmwareVersion(device, client, systemSettings),config.db)
    # Open peripheral connection    
    # Initialisation  -------
    #connect device
    print("\n-----connecting device-----")
    for i in range(0,4):
        status = ConnectToDevice(bleAddress, peripheral)
        if status != False:
            break
        time.sleep(3)
        if i == 3:
            raise cls.BluetoothError("unable to connect to device")
    print("\n-----getting characteristics-----")
    characteristics = peripheral.getCharacteristics() 
    #populating object to hold characteristics   
    print("populating characteristics")
    oadCharacteristics = OadCharacteristics()
    for char in characteristics:
        if char.uuid == oadCharacteristicUuid["blePinChar"]:
            handle = char.getHandle()
            oadCharacteristics.AddBlePin(char.uuid, char, handle)
        if char.uuid == oadCharacteristicUuid["imageIdentifyChar"]:
            handle = char.getHandle()
            oadCharacteristics.AddImageIdentify(char.uuid, char, handle)
        if char.uuid == oadCharacteristicUuid["imageBlockChar"]:
            handle = char.getHandle()
            oadCharacteristics.AddImageBlock(char.uuid, char, handle)
        if char.uuid == oadCharacteristicUuid["oadExtControlChar"]:
            handle = char.getHandle()
            oadCharacteristics.AddOadControl(char.uuid, char, handle)
        if char.uuid == oadCharacteristicUuid["commands"]:
            handle = char.getHandle()
            oadCharacteristics.AddCommands(char.uuid, char, handle)
        if char.uuid == oadCharacteristicUuid["deviceData"]:
            handle = char.getHandle()
            oadCharacteristics.AddDeviceData(char.uuid, char, handle)

    CheckCharacteristics(oadCharacteristics)
    # write Ble Pin
    print("\n-----Writing pin-----")
    try:
        oadCharacteristics.blePin.char.write(config.bleCmd["blepin"])
        pin = oadCharacteristics.blePin.char.read()
        print(pin)
    except:
        raise cls.BluetoothError("No ble pin characteristic")
    # enable OAD image identify notifications1
    EnableNotifications(oadCharacteristics, peripheral)
    delegate = MyDelegate(oadCharacteristics, oadReturnValues)
    try:
        peripheral.setDelegate(delegate)
    except Exception as err:
        print(err)
        raise cls.OadError("Problem setting delegate")
    
    # Get Oad Image status
    print("\n----- Write OAD Command to BF code-----")
    data = oadCharacteristics.deviceData.char.read()
    print(data)
    thisVersion = device.get('versions.tiFirmware')  
    if thisVersion== "1.0.0":
        print("version 1.0.0")
        oadCharacteristics.commands.char.write(b'\x80\x00\x00\x00\x00')
        time.sleep(20)
    else:
        data = oadCharacteristics.deviceData.char.read()
        if data[11] != 1:
            oadCharacteristics.commands.char.write(b'\x00\x00\x07')
            intResp = HandleNotification(peripheral, oadQueue, waitForNotificationTime, 0x01, False,  "retry")
        else:
            print("oad event in progress")
    # Wait for Oad Ready notification
    #while(1):
    #    try:
    #        data = oadCharacteristics.deviceData.char.read() 
    #        print(data) 
    #        if data[11] != 0:
    #            break   
    #        time.sleep(1)  
    #    except:
    #        status = ConnectToDevice(bleAddress, peripheral)
    if thisVersion != "2.2.3":
    # Wait for Oad Ready
        while(1):
            try:
                data = oadCharacteristics.deviceData.char.read() 
                print(data) 
                if data[11] != 0:
                    break   
                time.sleep(1)  
            except:
                status = ConnectToDevice(bleAddress, peripheral)
    else:
        time.sleep(5)

    #set MTU size

    print("\n----- Setting MTU -----")  
    peripheral.setMTU(248)
    # Erase previous bonds
    ErasePreviousBonds(oadCharacteristics, waitForNotificationTime, peripheral, oadQueue)
    # Get Oad Image status
    GetOadImageStatus(oadCharacteristics, waitForNotificationTime, peripheral, oadQueue)
    #get Oad Block size
    blockSize = GetBlockSize(oadCharacteristics, waitForNotificationTime, peripheral, oadQueue) 
    #Write image header
    WriteImageHeader(image, oadCharacteristics, waitForNotificationTime, peripheral, oadQueue)           
    # Send start OAD command  
    SendStartOadCommand(oadCharacteristics, waitForNotificationTime, peripheral, oadQueue)    
    #divide into blocks
    image.MakeBlocks(blockSize)
   
    #write blocks
    WriteBlocks(image, oadCharacteristics, waitForNotificationTime, peripheral, oadQueue)
    #get image status
    GetImageStatus(oadCharacteristics, waitForNotificationTime, peripheral, oadQueue)
    #enable OAD image
    print("Enabling oad image")
    oadCharacteristics.oadControl.char.write(bytes(controlCharacteristic["command"]["enableOadImage"]))
    print("Oad Done")
    peripheral.disconnect()

