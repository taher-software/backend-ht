import bcrypt


# Function to hash a password
def hash_password(password: str) -> str:
    # Generate a salt
    salt = bcrypt.gensalt()
    # Hash the password
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def check_password(password: str, hashed_password: str) -> bool:
    # Check if the provided password matches the hashed password
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
