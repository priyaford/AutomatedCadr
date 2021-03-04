def check():
    datafile = 'oadLog20201217.log'
    passCounter = 0
    failCounter = 0
    with open(datafile) as f:
        data = f.readlines()
        for line in data:
            if 'pass' in line:
                passCounter+=1   
            if 'fail' in line:
                failCounter+=1   
    print("Pass: ", passCounter, " Fail: ", failCounter)

check()