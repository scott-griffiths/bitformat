
__all__ = []


def parse_name_to_name_and_modifier(name: str) -> tuple[str, str]:
    modifiers = name.split("_")
    if len(modifiers) == 1:
        return name, ""
    if len(modifiers) == 2:
        return modifiers[0], modifiers[1]
    raise ValueError(f"Can't parse Dtype name '{name}' as more than one '_' is present.")
