import time


def _now():
    return time.strftime("%H:%M:%S")


def log(level: str, msg: str):
    print(f"[{_now()}] [{level}] {msg}")


def info(msg: str):
    log("INFO", msg)


def warn(msg: str):
    log("WARN", msg)


def error(msg: str):
    log("ERROR", msg)
