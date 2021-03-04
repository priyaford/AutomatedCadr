def CalculateResistanceFromVoltage(adc0Val, adc1Val):
    R1 = 470000.0
    R2 = 470000.0
    R4 = 470000.0
    Vg = adc1Val-adc0Val
    Vs = adc1Val*2
    Rx = ( (R2*Vs) - ((R1+R2)*Vg) )/( (R1*Vs) + ( (R1+R2)*Vg)) *R4
    
    print(Rx)

adc0 = 1271
adc1 = 1271
CalculateResistanceFromVoltage(adc0,adc1)

#adc0: 473, adc1: 1272