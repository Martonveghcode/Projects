msg="""marton is very cool
and i like ts 
hello"""
print(msg.find('marton'))
print(msg.replace('marton', 'C'))
msg1 = msg.replace('marton', 'c') 
print(msg1)

print('marton' in msg)
print(f"martons is {msg1.capitalize()}")