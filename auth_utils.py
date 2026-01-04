from werkzeug.security import generate_password_hash, check_password_hash
from database import add_user, get_user

def register_user(email, password):
    # check if email already exists
    if get_user(email):
        return False  # user already exists

    add_user(email, generate_password_hash(password), "patient")
    return True


def authenticate(email, password):
    user = get_user(email)
    if user and check_password_hash(user[2], password):
        return user
    return None
