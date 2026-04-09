from contextvars import ContextVar

request_language: ContextVar[str] = ContextVar("request_language", default="en")

def get_language() -> str:
    return request_language.get()

def set_language(lang: str):
    request_language.set(lang)
