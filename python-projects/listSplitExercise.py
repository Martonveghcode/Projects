csv= 'Eric,Jogn,Micheal,Terry,Graham:TerryG;Brian'
friends_list = ['Exercise: FIll me with names']

csv = csv.split(',')
csv = ' '.join(csv)
csv = csv.split(':')
csv = ' '.join(csv)
csv = csv.split(';')
csv = ' '.join(csv)

friends_list = csv
print(friends_list)

