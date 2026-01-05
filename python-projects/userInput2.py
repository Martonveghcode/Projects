kM = float(input("type your distance in Km"))
name = str(input("your first name"))
capName = name.capitalize()

mile = kM / 1.609
print(f" Hello {capName}, you inputted {kM} KM and you got {round(mile, 1)} miles, thank you for converting with us.")
3