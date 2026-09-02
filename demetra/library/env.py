import re


ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
MAX_ENV_KEY_LENGTH = 128
MAX_ENV_VALUE_LENGTH = 8192
