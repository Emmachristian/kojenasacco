# utils/templatetags/custom_filters.py

from django import template

register = template.Library()


@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except Exception:
        return 0


@register.filter
def div(value, arg):
    try:
        return float(value) / float(arg) if float(arg) != 0 else 0
    except Exception:
        return 0


@register.filter
def selectattr(iterable, args):
    """
    Usage:
        {{ items|selectattr:"field,value" }}
    Example:
        {{ memberships|selectattr:"is_active,True" }}
    """
    if not iterable or not args:
        return []

    try:
        attr, expected = args.split(',', 1)
    except ValueError:
        return []

    expected = expected.strip()

    def matches(obj):
        value = getattr(obj, attr, None)
        return str(value) == expected

    return filter(matches, iterable)


@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary using key.
    Usage: {{ my_dict|get_item:key_variable }}
    Example: {{ step_names|get_item:step_key }}
    """
    if not dictionary:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None