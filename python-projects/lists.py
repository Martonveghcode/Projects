marton = ["cool", "sexy", "tall"]
cars = [911,130,328,535,740,308]
print(marton[0])
print(marton)
print(marton[1:3])
print(len(marton))
print(marton.index("sexy"))
print(marton.count("sexy"))
cars.sort(reverse=True)
print(cars)
marton.reverse()
print(min(cars))
print(max(cars))
print(sum(cars))
cars.append(9112)
cars.pop()
print(cars)
del cars[2]
