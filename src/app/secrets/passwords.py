import bcrypt
import secrets
import string


# Function to generate a password
def generate_password() -> dict[str, str]:
    """
    Generate a cryptographically secure random 8-character password.

    Returns:
        dict[str, str]: Dictionary with keys:
            - "plain_password": Send to user via email/SMS (never store)
            - "hashed_password": Store in database
    """
    # Generate cryptographically secure random password
    alphabet = string.ascii_letters + string.digits  # A-Z, a-z, 0-9 (62 characters)
    plain_password = "".join(secrets.choice(alphabet) for _ in range(8))

    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)

    return {"plain_password": plain_password, "hashed_password": hashed.decode("utf-8")}


def hash_password(password: str) -> dict[str, str]:
    """
    Hash a given password.

    Args:
        password (str): The plain text password to hash.

    Returns:
        dict[str, str]: Dictionary with keys:
            - "plain_password": The original plain text password
            - "hashed_password": The hashed password to store in database
    """
    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)

    return hashed.decode("utf-8")


def check_password(password: str, hashed_password: str) -> bool:
    # Check if the provided password matches the hashed password
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
