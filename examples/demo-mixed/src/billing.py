"""A small, deliberately mixed-status module for the autodocstrings demo."""


def capitalise_plan_name(name: str) -> str:
    """Capitalises the plan name."""
    return name[:1].upper() + name[1:]


def total_with_tax(subtotal: float, tax_rate: float) -> float:
    return subtotal * (1 + tax_rate)


def apply_discount(price: float, tier: int) -> float:
    """Applies the tier discount to a price."""
    if tier == 3:
        return price * 0.85
    return price
