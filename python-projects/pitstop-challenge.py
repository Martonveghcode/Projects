totalRaceTime = float(input("whats the total race time? IN minutes"))
pitStopsMade = int(input("how many pitstops did you make?"))
averagePitStopDuration= float(input("whats the average duration in seconds"))

totalPitTime = pitStopsMade * averagePitStopDuration *60
pitsPercentage = totalRaceTime / totalPitTime * 100
pitsPercentage = round(pitsPercentage, 2)

print(f"your total pit stop time in seconds was: {totalPitTime}")
print(f"percentage of race time spent in pits is: {pitsPercentage}")
if(pitsPercentage > 5):
    print(f"get a new pit crew:(")
