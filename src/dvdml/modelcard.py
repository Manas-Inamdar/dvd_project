"""Read and override parameters of the BSIM4 `.model nmos` / `.model pmos` cards."""
import re

_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"


def split_cards(text: str) -> dict[str, str]:
    """Return {'nmos': card_text, 'pmos': card_text} (each includes its '.model' line)."""
    parts = re.split(r"(?im)^(?=\.model\s)", text)
    cards = {}
    for p in parts:
        m = re.match(r"(?i)\.model\s+(\w+)\s+(\w+)", p)
        if m:
            cards[m.group(2).lower()] = p.rstrip() + "\n"
    return cards


def _param_re(name: str) -> re.Pattern:
    # name must be a whole token followed by '=' (so 'xj' never matches 'xjbvs', 'u0' never 'ua' ...)
    return re.compile(rf"(?<![\w.])({re.escape(name)})(\s*=\s*)({_NUM})", re.IGNORECASE)


def get_param(card: str, name: str) -> float:
    m = _param_re(name).search(card)
    if not m:
        raise KeyError(f"parameter {name!r} not found in model card")
    return float(m.group(3))


def set_params(card: str, values: dict[str, float]) -> str:
    """Return card with the given parameters replaced (each must already exist exactly once)."""
    for name, val in values.items():
        rx = _param_re(name)
        if len(rx.findall(card)) != 1:
            raise ValueError(f"parameter {name!r} must appear exactly once in the card")
        card = rx.sub(lambda m, v=val: f"{m.group(1)}{m.group(2)}{v:.9e}", card, count=1)
    return card


def nominals(text: str, params: list[str]) -> dict[str, dict[str, float]]:
    cards = split_cards(text)
    return {t: {p: get_param(cards[t], p) for p in params} for t in ("nmos", "pmos")}
