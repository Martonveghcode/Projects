CustomerName = "marton"
NumberOfPasses = 16
TokensPerPass = 2
pricePerPass = 3         # this is in euros i assume 
tokensPerGame = 3

totalTokens = NumberOfPasses * TokensPerPass
totalCost = NumberOfPasses * pricePerPass # in euro
gamesAvailable = (NumberOfPasses * TokensPerPass) // tokensPerGame 

print(f"you are called  {CustomerName}  you have    {NumberOfPasses} , you have {totalTokens} , it will cost you {totalCost} and you have {gamesAvailable} games available")