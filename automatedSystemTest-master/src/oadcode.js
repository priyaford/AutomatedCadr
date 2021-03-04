
import { firebase } from "@modules/Firebase"
import { logOadAttempt } from "@modules/DeviceActions"

import * as Constants from "./Constants"
import * as Controller from "./Controller"
import Bluetooth from "./SimpleBluetooth"

const { Buffer } = require("buffer/")

// This should be the actual image information sent per block
// block size minus header
let dataPerBlock = 0

/*
  Block size be lower than or equal to connection MTU minus 3. (MTU == 247, OAD_ATT_OVERHEAD == 3)
  If MTU is 247, block size cannot be more than 244.
  Block size should be equal to the block size constant in the tracker firmware.
*/

export default async ({ deviceId, blePin, meta, data, blockSize, installedVersion, nextVersion, onProgress }) => {
  console.log("Updating formware for " + deviceId)
  if (!data) throw new Error("Missing data")

  dataPerBlock = blockSize - 4 // Header size is 4
  console.log("Block size: " + blockSize)

  onProgress?.(0)

  try {
    const { device } = await Bluetooth.findAndConnect({ deviceId, blePin, options: { requestMTU: blockSize + 4 } })

    onProgress?.(0.05)
    if (Bluetooth.isCancelled()) throw new Error("cancelled")

    const requiredLevel = firebase.remoteConfig().getValue("requiredBatteryLevelForOad").value
    console.log("Required battery level is " + requiredLevel + "% or higher")

    console.log("Reading battery level")
    const batteryValue = (await Controller.readBatteryLevel(device)).readUInt8(0)
    const batteryLevel = batteryValue >= 128 ? batteryValue - 128 : batteryValue

    console.log("Battery level is " + batteryLevel + "%")
    if (batteryLevel < requiredLevel) throw new Error("Battery level too low. " + requiredLevel + "% or more is required.")

    if (Bluetooth.isCancelled()) throw new Error("cancelled")

    const versionsThatNeedOadCommand = ["1.0.0", "1.2.0", "2.0.45", "2.0.46", "2.1.0"]
    if (versionsThatNeedOadCommand.includes(installedVersion)) {
      console.log("Writing BikeFinder's oad command byte")
      const values = Bluetooth.getCommandValues({ command: "oad", version: installedVersion })
      await Controller.writeCommands({ device, values })
    }

    onProgress?.(0.1)
    if (Bluetooth.isCancelled()) throw new Error("cancelled")

    if (installedVersion.startsWith("1.")) {
      await new Promise(res => setTimeout(res, 7000))
    }
    onProgress?.(0.2)

    if (Bluetooth.isCancelled()) throw new Error("cancelled")
    console.log("Verifying image header")
    await verifyHeader({ device, data, meta })
    onProgress?.(0.3)

    if (Bluetooth.isCancelled()) throw new Error("cancelled")
    console.log("Transferring image data")
    await writeImage({ device, data, onProgress: prog => onProgress?.(0.3 + prog * 0.7) })
    console.log("OAD complete")

    logOadAttempt({ deviceId, meta, blockSize, installedVersion, nextVersion })
  } catch (err) {
    console.log("Failed to update firmware: ", err)
    logOadAttempt({ deviceId, meta, blockSize, installedVersion, nextVersion, err })
    throw err
  } finally {
    Bluetooth.disconnect()
  }
}

const verifyHeader = ({ device, data, meta }) => new Promise((resolve, reject) => {
  const metadata = Buffer.alloc(22)
  data.copy(metadata, 0, 0, 8)

  metadata.writeUInt8(meta.bimVersion || 0x01, 8)
  metadata.writeUInt8(meta.metadataVersion || 0x01, 9)
  metadata.writeUInt8(meta.copyStatus || 0xff, 10)
  metadata.writeUInt8(meta.crcStatus || 0xff, 11)
  metadata.writeUInt8(meta.imageType || 0x01, 12) // 0x01 == app, 0x02 == stack, 0x03 == merged
  metadata.writeUInt8(meta.imageNumber || 0x01, 13)

  metadata.writeUInt32LE(data.length, 14)

  metadata.writeUInt8(meta.stackRelease1 || 0x30, 18)
  metadata.writeUInt8(meta.stackRelease2 || 0x30, 19)
  metadata.writeUInt8(meta.appRelease1 || 0x30, 20)
  metadata.writeUInt8(meta.appRelease2 || 0x31, 21)

  // 4F:41:44:20:49:4D:47:20 :01:01:FF:FF:01:01 :55:1F:01:00 :30:30:30:31

  let listener = null
  const onError = err => {
    listener && listener.remove()
    reject(err)
  }
  const onSuccess = () => {
    listener && listener.remove()
    resolve()
  }

  console.log("Monitoring image_identify")
  listener = device.monitorCharacteristicForService(
    Constants.oadService,
    Constants.oadCharacteristics.image_identify,
    (err, res) => {
      try {
        if (Bluetooth.isCancelled()) throw new Error("cancelled")
        if (err) throw err
        const val = Buffer.from(res.value, "base64").readUInt8(0)
        console.log("Notify image_identify: ", val)
        if (val !== 0) throw new Error(val + ": " + RESPONSES[val])
        return onSuccess()
      } catch (err2) {
        console.log("image_identify notify error: ", err2)
        return onError(err2)
      }
    }
  )

  console.log("Writing metadata: ", metadata.toString("hex"))
  device.writeCharacteristicWithoutResponseForService(
    Constants.oadService,
    Constants.oadCharacteristics.image_identify,
    metadata.toString("base64"),
  )
    .catch(onError)
})

const writeImage = ({ device, data, onProgress }) => new Promise((resolve, reject) => {
  const totalBlocks = Math.floor(data.length / dataPerBlock)

  let listener = null
  const onError = err => {
    listener && listener.remove()
    reject(err)
  }
  const onSuccess = () => {
    listener && listener.remove()
    console.log("Image transfer complete")
    resolve()
  }

  console.log("Monitoring image_control")
  listener = device.monitorCharacteristicForService(
    Constants.oadService,
    Constants.oadCharacteristics.image_control,
    async (err, res) => {
      try {
        if (Bluetooth.isCancelled()) throw new Error("cancelled")
        if (err) throw err

        const buff = Buffer.from(res.value, "base64")

        // Documentation: http://software-dl.ti.com/simplelink/esd/simplelink_cc2640r2_sdk/1.50.00.58/exports/docs/blestack/ble_user_guide/html/oad-ble-stack-3.x/oad_profile.html#sec-oad-error-codes
        const commandId = buff.readUInt8(0)

        // OAD block size response
        if (commandId === 0x01) {
          const blockSize = buff.readUInt8(1)
          return console.log("Block size: ", blockSize)
        }

        

        // Image Block Write Char Response
        if (commandId === 0x12) {
          const status = buff.readUInt8(1)

          // Status OK. The block was successfully written. Now write next block.
          if (status === 0) {
            const blockNum = buff.readUInt32LE(2)
            onProgress?.(blockNum / totalBlocks)
            return writeBlock({ device, data, blockNum }).catch(onError)
          }

          // OAD image payload download complete
          if (status === 14) {
            console.log("Image transfer complete. Writing command to boot from image")
            return device.writeCharacteristicWithoutResponseForService(
              Constants.oadService,
              Constants.oadCharacteristics.image_control,
              Buffer.from([0x04]).toString("base64"),
            ).catch(onError)
          }
          
          // Enable OAD Image Response
        if (commandId === 0x04) {
          const status = buff.readUInt8(1)

          // Status OK. Device is now running with new image. Success!
          if (status === 0) return onSuccess()

          throw new Error("Unknown status from Enable Image command: " + status)
        }

          // Unexpected status, probably an error code
          throw new Error("Block write was unsuccessful. Status: " + status + ".")
        }

        // Unexpected command id.
        throw new Error("Unexpected command id: " + commandId)
      } catch (err2) {
        console.log("image_control notify error: ", err2)
        return onError(err2)
      }
    }
  )

  // Send a "get OAD block size" command. Response will be received in the monitor, with ID 0x01.
  console.log("Writing command to get OAD block size. CommandId is 0x01.")
  return device.writeCharacteristicWithoutResponseForService(
    Constants.oadService,
    Constants.oadCharacteristics.image_control,
    Buffer.from([0x01]).toString("base64"),
  )
    .then(() => {
      console.log("Writing start OAD command")
      return device.writeCharacteristicWithoutResponseForService(
        Constants.oadService,
        Constants.oadCharacteristics.image_control,
        Buffer.from([0x03]).toString("base64"),
      )
    })
    .catch(onError)
})

const writeBlock = ({ device, data, blockNum }) => {
  const blockStart = blockNum * dataPerBlock

  const dataLength = blockStart + dataPerBlock <= data.length
    ? dataPerBlock
    : data.length - blockStart

  const writeBuffer = Buffer.alloc(dataLength + 4)
  writeBuffer.writeUInt32LE(blockNum, 0)

  data.slice(blockStart, blockStart + dataLength).copy(writeBuffer, 4)

  // console.log("Writing block data: ", writeBuffer)
  console.log("Writing block data for block " + blockNum + ": ", writeBuffer)
  return device.writeCharacteristicWithoutResponseForService(
    Constants.oadService,
    Constants.oadCharacteristics.image_block,
    writeBuffer.toString("base64"),
  )
}

const RESPONSES = [
  "OAD succeeded", // OAD_SUCCESS
  "The downloaded image’s CRC doesn’t match the one expected from the metadata", // OAD_CRC_ERR
  "Flash function failure such as flashOpen/flashRead/flash write/flash erase", // OAD_FLASH_ERR
  "The block number of the received packet doesn’t match the one requested, an overflow has occurred.", // OAD_BUFFER_OFL
  "OAD start command received, while OAD is already is progress", // OAD_ALREADY_STARTED
  "OAD data block received with OAD start process", // OAD_NOT_STARTED
  "OAD enable command received without complete OAD image download", // OAD_DL_NOT_COMPLETE
  "Memory allocation fails/ used only for backward compatibility", // OAD_NO_RESOURCES
  "Image is too big", // OAD_IMAGE_TOO_BIG
  "Stack and flash boundary mismatch, program entry mismatch", // OAD_INCOMPATIBLE_IMAGE
  "Invalid image ID received", // OAD_INVALID_FILE
  "BIM/image header/firmware version mismatch", // OAD_INCOMPATIBLE_FILE
  "Start OAD process / Image Identify message/image payload authentication/validation fail", // OAD_AUTH_FAIL
  "Data length extension or OAD control point characteristic not supported", // OAD_EXT_NOT_SUPPORTED
  "image payload download complete", // OAD_DL_COMPLETE
  "Internal (target side) error code used to halt the process if a CCCD has not been enabled", // OAD_CCCD_NOT_ENABLED
  "OAD Image ID has been tried too many times and has timed out. Device will disconnect.", // OAD_IMG_ID_TIMEOUT
]