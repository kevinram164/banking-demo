from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw: str) -> str:
    return pwd.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd.verify(pw, hashed)
