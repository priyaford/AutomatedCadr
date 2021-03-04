numbers = bytes([0xff,0xff,0xAF,0xFF])
print(numbers, type(numbers))
number1 = int.from_bytes(numbers[0:2],"big")
number2 = int.from_bytes(numbers[2:4],"big")<<16
print(number1 | number2)