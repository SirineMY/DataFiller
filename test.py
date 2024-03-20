import bcrypt

password = "secret"
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
print(hashed)

# Vérification
if bcrypt.checkpw(password.encode(), hashed):
    print("Match")
else:
    print("Does not match")
