"""Evaluate the arithmetic in a figure spec, without evaluating anything else.

A book declares a curve as a string — ``"(x^2 - 1)/(x - 1)"`` — which has to become a
callable. Handing that to :func:`eval` would let a config file run arbitrary code, so
instead the expression is parsed to a syntax tree and walked with a whitelist: only
arithmetic, comparisons, conditionals, a fixed set of maths functions and a fixed set of
constants are permitted. Anything else — an attribute, a subscript, an unlisted name — is
a :class:`ExpressionError`, not a silent surprise.

``^`` means exponentiation here, as it does in every other mathematical notation, so it
is rewritten to ``**`` before parsing.

    >>> f = compile_expr("(x^2 - 1)/(x - 1)")
    >>> f(3.0)
    4.0
"""
from __future__ import annotations

import ast
import math

#: Functions a figure may call.
FUNCTIONS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "exp": math.exp, "log": math.log, "ln": math.log, "log10": math.log10,
    "log2": math.log2, "sqrt": math.sqrt, "hypot": math.hypot,
    "abs": abs, "floor": math.floor, "ceil": math.ceil, "round": round,
    "min": min, "max": max, "pow": math.pow, "copysign": math.copysign,
    "degrees": math.degrees, "radians": math.radians, "erf": math.erf,
    "gamma": math.gamma, "factorial": math.factorial,
}

#: Constants a figure may name.
CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf}

_BINARY = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}
_UNARY = {ast.UAdd: lambda a: +a, ast.USub: lambda a: -a}
_COMPARE = {
    ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b,
}


class ExpressionError(Exception):
    """An expression is malformed, or reaches for something it may not have."""


def _evaluate(node, variables):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, variables)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ExpressionError(f"only numbers may appear literally, not {node.value!r}")

    if isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        known = ", ".join(sorted(set(variables) | set(CONSTANTS)))
        raise ExpressionError(f"unknown name '{node.id}' (known: {known})")

    if isinstance(node, ast.BinOp):
        op = _BINARY.get(type(node.op))
        if op is None:
            raise ExpressionError(f"operator {type(node.op).__name__} is not allowed")
        return op(_evaluate(node.left, variables), _evaluate(node.right, variables))

    if isinstance(node, ast.UnaryOp):
        op = _UNARY.get(type(node.op))
        if op is None:
            raise ExpressionError(f"operator {type(node.op).__name__} is not allowed")
        return op(_evaluate(node.operand, variables))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ExpressionError("only plain function calls are allowed")
        fn = FUNCTIONS.get(node.func.id)
        if fn is None:
            raise ExpressionError(f"unknown function '{node.func.id}'")
        if node.keywords:
            raise ExpressionError("functions take positional arguments only")
        return fn(*[_evaluate(a, variables) for a in node.args])

    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, variables)
        for op, comparator in zip(node.ops, node.comparators):
            fn = _COMPARE.get(type(op))
            if fn is None:
                raise ExpressionError(f"comparison {type(op).__name__} is not allowed")
            right = _evaluate(comparator, variables)
            if not fn(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        values = [_evaluate(v, variables) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)

    if isinstance(node, ast.IfExp):        # piecewise: "x if x > 0 else -x"
        chosen = node.body if _evaluate(node.test, variables) else node.orelse
        return _evaluate(chosen, variables)

    raise ExpressionError(f"{type(node).__name__} is not allowed in an expression")


def compile_expr(source, variable="x"):
    """Compile *source* into a one-argument callable. Raises on anything unsafe."""
    text = str(source).replace("^", "**")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"cannot parse {source!r}: {exc.msg}") from exc

    def evaluate(value):
        return _evaluate(tree, {variable: value})

    evaluate.source = source
    return evaluate


def evaluate(source, **variables):
    """Evaluate *source* once, with the given variables bound."""
    text = str(source).replace("^", "**")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"cannot parse {source!r}: {exc.msg}") from exc
    return _evaluate(tree, variables)


def as_number(value):
    """Accept a number or an expression string and return a float."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return float(evaluate(value))
