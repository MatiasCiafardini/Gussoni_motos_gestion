def tail_ellipsis(text: str, max_len: int = 10) -> str:
    """
    Devuelve los últimos `max_len` caracteres,
    anteponiendo '...' si el texto es más largo.
    """
    if not text:
        return ""
    text = str(text)
    if len(text) <= max_len:
        return text
    return "..." + text[-max_len:]
