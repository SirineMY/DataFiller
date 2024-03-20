from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["sha256_crypt"], 
    deprecated="auto"
)


# Fonction pour hacher le mot de passe
def hash_password(password: str):
    return pwd_context.hash(password)

# Fonction pour vérifier le mot de passe
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)
