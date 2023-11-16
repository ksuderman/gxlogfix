import ast
import re

LOGGER_NAMES = ["log", "logger", "logging"]
LOGGER_METHODS = ["trace", "debug", "info", "warn", "warning", "error", "critical", "exception"]


class Patch:
    """
    A Patch object contains the line and column information needed to replace a
    line of code.
    """

    def __init__(self, line, end_line, offset, statement):
        self.line = line
        self.end_line = end_line
        self.offset = offset
        self.statement = statement

    def render(self):
        pad = " " * self.offset
        return pad + self.statement


def is_log_method(node: ast.AST):
    """
    Check if the code tree rooted at ``node`` represents a call to the
    logging framework.

    :param node: the root node of the expression to check
    :return: True if this ``node`` represents a logging call, False otherwise.
    """
    if not isinstance(node, ast.Call):
        return False
    if hasattr(node, "func"):
        if hasattr(node.func, "value"):
            if hasattr(node.func.value, "id"):
                return (
                    node.func.value.id in LOGGER_NAMES
                    and node.func.attr in LOGGER_METHODS
                )
    return False


def get_format_spec(v: ast.FormattedValue) -> str:
    """
    Get the format specifier to use when performing substitution on ``f-string``
    objects. Only very basic format strings are supported.

    :param v: the formatted value that appears in the f-string.
    :return: an equivalent % format specifier or None if it is an unsupported
             format specifier.
    """
    if v.format_spec is None:
        return "%s"
    spec = v.format_spec.values[0].value
    if "d" in spec or "f" in spec:
        return "%" + spec
    if spec.isdigit():
        return f"%{spec}s"
    c = spec[:1]
    if c == "<":
        return f"%-{spec[1:]}s"
    if c == ">":
        return f"%{spec[1:]}s"
    return None


def get_name_or_value(e: ast.AST) -> str:
    """
    Used on terminal nodes when we need to get the name/value from an
    ``ast.Name`` or ``ast.Constant`` object.

    :param e: the node to check
    :return: a string containing the name or constant value.
    """
    if isinstance(e, ast.Name):
        return e.id
    return str(e.value)


def is_str_format(node: ast.AST) -> bool:
    """
    Check if this is a call to ``str.format()``.

    :param node: the code to check
    :return: True if this node represents a call to ``str.format``, False
             otherwise
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    )


def skip(path: str, node: ast.AST) -> None:
    """Report that we are not patching this logging statement."""
    print(f"Skipping {path} {node.lineno} {ast.unparse(node)}")


def get_patch(source: str, path: str) -> dict:
    """
    Parses the source code into an abstract syntax tree and the walks the tree
    looking for calls to the logging framework. A ``Patch`` object will be
    created for every logging call that does greedy string interpolation with an
    ``f-string``, ``str.format()``, or with the modulo operator (%).

    :param source: a string containing Python source code.
    :param path: the name and path of the source file.  Used in messages only.
    :return: a dictionary of Patch objects, if any, that should be applied to
             the source file. Line numbers are used as keys into the dictionary.
    """
    patches = {}
    tree = ast.parse(source, path)
    # Walk the source tree looking for logging calls.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_log_method(node):
            if len(node.args) != 1:
                # If the logging call has more than one arg then it is not
                # one of the cases we handle.  That is, it (likely) already uses
                # lazy string interpolation.
                continue
            method_call = f"{node.func.value.id}.{node.func.attr}"
            arg = node.args[0]
            if is_str_format(arg):
                if isinstance(arg.func.value, ast.Constant) and len(arg.keywords) == 0:
                    # We only handle cases where the LHS is a literal string
                    # constant with no keyword substitutions.
                    format_string = re.sub(
                        r"{\s*}",
                        "%s",
                        arg.func.value.value,
                    )
                    if "{" in format_string:
                        # There is some sort of funky formatting going on.
                        skip(path, node)
                    else:
                        node.args = list()
                        node.args.append(ast.Constant(format_string))
                        node.args.extend(arg.args)
                        patch = Patch(
                            node.lineno,
                            node.end_lineno,
                            node.col_offset,
                            ast.unparse(node)
                        )
                        patches[patch.line] = patch
                else:
                    skip(path, node)
            elif isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod):
                node.args = list()
                node.args.append(arg.left)
                if isinstance(arg.right, ast.Tuple):
                    node.args.extend(arg.right.elts)
                else:
                    node.args.append(arg.right)
                patch = Patch(
                    node.lineno, node.end_lineno, node.col_offset, ast.unparse(node)
                )
                patches[patch.line] = patch
            elif isinstance(arg, ast.JoinedStr):
                args = []
                format_string = ""
                for v in arg.values:
                    if isinstance(v, ast.FormattedValue):
                        args.append(v.value)
                        format_string += get_format_spec(v)
                    elif isinstance(v, ast.Constant):
                        format_string += v.value
                    else:
                        # TODO: Should skip() here?
                        raise Exception(f"Unknown value: {v} type: {type(v)}")
                node.args = list()
                node.args.append(ast.Constant(format_string))
                node.args.extend(args)
                patch = Patch(
                    node.lineno, node.end_lineno, node.col_offset, ast.unparse(node)
                )
                patches[patch.line] = patch
    return patches


def write_patched_file(path: str, patches: dict, source: str) -> None:
    """
    Writes Python source code to a file applying patches as needed.

    :param path:    the path to the file to be written
    :param patches: the patches to be applied
    :param source:  the Python source code to be patched
    :return:        None
    """
    if len(patches) == 0:
        return
    lines = source.splitlines(keepends=False)
    with open(path, "w") as f:
        index = 0
        while index < len(lines):
            lineno = index + 1
            if lineno in patches:
                patch = patches[lineno]
                f.write(patch.render() + "\n")
                patch_length = patch.end_line - patch.line
                index += patch_length
            else:
                f.write(lines[index] + "\n")
            index += 1


def patch_file(path: str) -> None:
    """
    Parse the source code in the file ``path`` and replace any logging
    statements that do greedy string interpolation with an equivalent logging
    statement that uses lazy string interpolation.

    If the source file does not contain any logging statements that do greedy
    string interpolation the file is left unmodified.  Otherwise, the existing
    file will be overwritten with the new content.

    :param path: the path to the source file to be patched.
    :return: None
    """
    # global n_patched_files, n_patched_lines
    with open(path) as f:
        source = f.read()
    # Get the lines, if any, that need to be re-written
    patches = get_patch(source, path)
    # Write new file if the current one needs patching.
    if len(patches) > 0:
        write_patched_file(path, patches, source)
    return len(patches)
