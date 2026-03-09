# Sửa file trong common, services, phase4, phase8 hoặc k8s-chatbot
# Ví dụ: thêm 1 dòng comment vào common/__init__.py hoặc file bất kỳimport os
from passlib.context import CryptContext

# Giảm rounds (mặc định 10) nếu CPU cao; 12 = an toàn hơn nhưng ~2x chậm
_rounds = int(os.getenv("BCRYPT_ROUNDS", "10"))
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=_rounds)

def hash_password(pw: str) -> str:
    return pwd.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd.verify(pw, hashed)
