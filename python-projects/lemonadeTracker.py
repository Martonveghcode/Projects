sales_w1 = [7,3,42,19,15,35,9]
sales_w2 = [12,4,26,10,7,28]
sales = []

sales_w2.append(int(input("sales for the day: ")))
sales = sales_w1 + sales_w2
print(f" your best day was :{max(sales)}")
print(f"your worst day was:{min(sales)}")
print(f"your sales for week 1: {sum(sales_w1) * 1.5}")
print(f"your sales for week 2:{sum(sales_w2) * 1.5}")
print(f"your sales in total: {sum(sales) * 1.5}")
