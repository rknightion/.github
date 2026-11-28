"""A small evaluator for the GitHub Actions expressions these tests read from workflows.

Supports what the release workflows use: string, number and boolean literals, context
paths (looked up in a dict), !, ==, !=, &&, ||, parentheses, contains(), startsWith()
and fromJSON(). && and || return an operand, as in Actions, so `a && 'x' || 'y'` works.
Anything else raises, so an unsupported expression fails the test instead of passing.
"""
import json
import re

TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|'((?:[^']|'')*)'|(&&|\|\||==|!=|!|\(|\)|,)|([A-Za-z_][\w.-]*))")


def tokenize(text):
    tokens, pos = [], 0
    text = text.strip()
    while pos < len(text):
        match = TOKEN.match(text, pos)
        if not match or match.end() == pos:
            raise ValueError(f"cannot tokenize {text[pos:]!r}")
        number, string, op, name = match.groups()
        if number is not None:
            tokens.append(("lit", float(number) if "." in number else int(number)))
        elif string is not None:
            tokens.append(("lit", string.replace("''", "'")))
        elif op is not None:
            tokens.append(("op", op))
        else:
            tokens.append(("name", name))
        pos = match.end()
    return tokens


def truthy(value):
    return value not in (False, 0, "", None)


def loose_equal(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    return a == b


def evaluate(expression, context):
    """Evaluate one expression; `context` maps dotted names (e.g. 'inputs.trivy') to values."""
    expression = expression.strip()
    if expression.startswith("${{") and expression.endswith("}}"):
        expression = expression[3:-2]
    tokens = tokenize(expression)
    position = [0]

    def peek():
        return tokens[position[0]] if position[0] < len(tokens) else (None, None)

    def take(expected=None):
        token = peek()
        if expected is not None and token != ("op", expected):
            raise ValueError(f"expected {expected!r}, got {token!r} in {expression!r}")
        position[0] += 1
        return token

    def lookup(name):
        if name in ("true", "false"):
            return name == "true"
        if name == "null":
            return None
        if name not in context:
            raise KeyError(f"no value for {name} in {expression!r}")
        return context[name]

    def call(name, args):
        if name == "contains":
            haystack, needle = args
            if isinstance(haystack, list):
                return any(loose_equal(item, needle) for item in haystack)
            return str(needle).lower() in str(haystack).lower()
        if name == "startsWith":
            return str(args[0]).lower().startswith(str(args[1]).lower())
        if name == "fromJSON":
            return json.loads(args[0])
        raise ValueError(f"unsupported function {name}")

    def primary():
        kind, value = take()
        if kind == "lit":
            return value
        if (kind, value) == ("op", "("):
            result = disjunction()
            take(")")
            return result
        if (kind, value) == ("op", "!"):
            return not truthy(primary())
        if kind == "name":
            if peek() == ("op", "("):
                take("(")
                args = []
                if peek() != ("op", ")"):
                    args.append(disjunction())
                    while peek() == ("op", ","):
                        take(",")
                        args.append(disjunction())
                take(")")
                return call(value, args)
            return lookup(value)
        raise ValueError(f"unexpected {value!r} in {expression!r}")

    def comparison():
        left = primary()
        while peek() in (("op", "=="), ("op", "!=")):
            op = take()[1]
            right = primary()
            left = loose_equal(left, right) if op == "==" else not loose_equal(left, right)
        return left

    def conjunction():
        left = comparison()
        while peek() == ("op", "&&"):
            take()
            right = comparison()
            left = right if truthy(left) else left
        return left

    def disjunction():
        left = conjunction()
        while peek() == ("op", "||"):
            take()
            right = conjunction()
            left = left if truthy(left) else right
        return left

    result = disjunction()
    if position[0] != len(tokens):
        raise ValueError(f"trailing tokens in {expression!r}")
    return result
