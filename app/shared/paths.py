import os
import sys

APP_NAME = "GussoniApp"


def is_frozen():
    return getattr(sys, 'frozen', False)


def base_path():
    if is_frozen():
        return sys._MEIPASS
    return os.path.abspath(".")


def user_data_path():
    return os.path.join(
        os.getenv("APPDATA"),
        APP_NAME
    )


def ensure_user_dirs():
    paths = [
        user_data_path(),
        os.path.join(user_data_path(), "certificados"),
        os.path.join(user_data_path(), "logs"),
    ]
    for p in paths:
        os.makedirs(p, exist_ok=True)
