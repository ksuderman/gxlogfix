import argparse
import logging
import os
import sys
import unittest

from logfix import *

SETUP = """import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('test.logger')
log.propagate = False
log.addHandler(handler)
"""

names_that_look_like_numbers = """attempts
count
errno
galaxy_job_id
i
id
index
job_id
len
lines
pid
port
sig
size
task_id
test_index
tool_exit_code
total
tries""".splitlines(
    keepends=False
)


def it_looks_like_a_number(name: str) -> bool:
    for x in names_that_look_like_numbers:
        if x in name:
            return True
    return False


class TestHandler(logging.StreamHandler):
    """
    A custom handler we will add to the logger to save the line that was
    logged in a public variable.
    """
    def __init__(self):
        logging.StreamHandler.__init__(self)
        self.line = None

    def emit(self, record):
        try:
            self.line = self.format(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class Expando:
    """
    A class that will add properties and methods as they are referenced.
    """
    def __init__(self, value="root", verbose=False):
        self.verbose = verbose
        if verbose:
            print(f"Creating an expando for {value}")
        self.cache = dict()
        self.value = value

    def __getattr__(self, item):
        if self.verbose:
            print(f"Getting attr {item}")
        if item not in self.cache:
            self.cache[item] = Expando(f"{self.value}.{item}")
        return self.cache[item]
        # return item

    def __getitem__(self, item):
        if self.verbose:
            print(f"Getting item {item}")
        return str(item)

    def __call__(self, *args, **kwargs):
        if self.verbose:
            print(f"Calling expando {self.value} with {type(args)} len {len(args)}")
        # a = ','.join(args)
        if it_looks_like_a_number(self.value):
            return 42
        return self.value + f"({args})"

    def __repr__(self):
        if self.verbose:
            print(f"Getting representation {self.value}")
        return self.value

    def __str__(self):
        if self.verbose:
            print(f"Getting expando string {self.value}")
        return self.value

    def __int__(self):
        if self.verbose:
            print(f"Getting expando int")
        return 42


def parse(source):
    return ast.parse(source, "__fake__.py").body[0].value


def collect_name(node: ast.AST):
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        prefix = collect_name(node.value)
        prefix.append(node.attr)
        return prefix
    raise TypeError(f"Unable to get type for {ast.unparse(node)}")


def add_type(attr: ast.AST, mock: dict):
    name = get_base_name(attr)
    update_mock(mock, name)


def get_base_name(node: ast.AST) -> str:
    while hasattr(node, "value") and isinstance(node.value, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    # I don't think this should ever happen, but we check just in case.
    if isinstance(node, ast.Constant):
        return node.value
    return node.value.id


def update_mock(mock, name):
    if name not in mock:
        mock[name] = Expando(name)


def create_mock_args(args: ast.AST, mock: dict) -> None:
    for arg in args:
        # TODO We probably need to handle ast.Subscript as well.
        if isinstance(arg, ast.Name):
            # mock[arg.id] = Expando(arg.id)
            update_mock(mock, arg.id)
        elif isinstance(arg, ast.Attribute):
            name = get_base_name(arg)
            update_mock(mock, name)
        elif isinstance(arg, ast.Call):
            create_mock_call(arg, mock)
        elif isinstance(arg, ast.Tuple):
            for e in arg.elts:
                create_mock_args(e, mock)


def create_mock_call(node: ast.Call, mock: dict) -> None:
    if isinstance(node.func, ast.Name):
        name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        name = get_base_name(node.func)
    else:
        raise TypeError(f"Unable to handle {type(node.func)}")
    update_mock(mock, name)
    create_mock_args(node.args, mock)


def create_mock(node: ast.AST) -> dict:
    """
    Create a dictionary of mock values that are referenced in the AST rooted
    at ``node``. This dictionary will be passed as the ``globals`` when calling
    the ``exec`` function to evaluate the logging call.

    :param node: an AST representing a call to the logging framework
    :return: a dictionary that can be used as the ``globals`` when this
    statement is executed.
    """
    mock = dict()
    # Add a few names for convenience
    mock["full_command"] = ["rm", "-rf", ".*"]
    mock["cmd"] = "ls"
    mock["qacct"] = list() #{"exit_status": 42}
    mock["self"] = Expando("self")
    mock["rows"] = list()
    mock["kwargs"] = dict()
    mock["sum"] = lambda x: 42
    mock['e'] = Expando('e')
    mock['ret_allow_action'] = list()
    mock['exc_info'] = 'exc_info'
    mock['message'] = '%s %s %s %s'
    # Add variable names used as format string
    mock["INSTANCE_ID_INVALID_MESSAGE"] = "Instance id %s is invalid"
    mock["LOAD_FAILURE_ERROR"] = "Failure loading %s"

    for arg in node.args[1:]:
        if isinstance(arg, ast.Name):
            if it_looks_like_a_number(arg.id):
                mock[arg.id] = 42
            else:
                mock[arg.id] = arg.id
        elif isinstance(arg, ast.Attribute):
            add_type(arg, mock)
        elif isinstance(arg, ast.Call):
            create_mock_call(arg, mock)
            # name = get_base_name(arg.func)
            # mock[name] = Expando(name)
            # create_mock_args(arg, mock)
        elif isinstance(arg, ast.Subscript):
            # mock[arg.slice.attr] = Expando(arg.slice.attr)
            update_mock(mock, arg.slice.attr)
        else:
            for child in ast.walk(arg):
                if isinstance(child, ast.Name):
                    if child.id not in mock:
                        mock[child.id] = Expando(child.id)
                elif isinstance(child, ast.Attribute):
                    # add_type(child, mock)
                    name = get_base_name(child)
                    # mock[name] = Expando()
                    update_mock(mock, name)
                elif isinstance(child, ast.Subscript):
                    if isinstance(child.value, ast.Name):
                        print(f"Adding name {child.value.id} to mock")
                        # mock[child.value.id] = Expando()
                        update_mock(mock, child.value.id)
                    else:
                        print(f"Adding child slice {child.slice.attr} to mock")
                        # mock[child.slice.attr] = Expando()
                        update_mock(mock, child.slice.attr)
                elif isinstance(child, ast.Call):
                    create_mock_call(child, mock)

    return mock


def evaluate(original_statement):
    patches = get_patch(original_statement, "test.py")
    patch = patches[1]
    print(patch.render())
    tree = parse(patch.render())
    mock = create_mock(tree)
    handler = TestHandler()
    mock["handler"] = handler
    exec(SETUP + original_statement, mock)
    print(handler.line)


passed = 0
skipped = list()
failed = list()
errored = list()


def test_patch(filepath: str, patches: dict, source: str):
    global passed, failed, errored, skipped
    if len(patches) == 0:
        return
    lines = source.splitlines(keepends=False)
    handler = TestHandler()
    for line_no in sorted(patches):  # .keys().sort():
        patch = patches[line_no]
        original = ""
        for i in range(patch.line, patch.end_line + 1):
            original += lines[i - 1].lstrip() + "\n"
        updated = patch.render().lstrip()
        updated_tree = parse(updated)
        try:
            mock_data = create_mock(updated_tree)
        except:
            print(f"Unable to create mock for {original}", end=None)
            skipped.append(original)
            continue
        mock_data["handler"] = handler
        try:
            exec(SETUP + updated, mock_data)
            updated_output = handler.line
            exec(SETUP + original, mock_data)
            original_output = handler.line
            if original_output != updated_output:
                print(f"ERROR: Output mismatch for {original}", end=None)
                failed.append(original)
            else:
                print(f"Passed: {original}", end=None)
                passed += 1
        except Exception as e:
            print(f"Error processing {original}", end=None)
            print(e)
            errored.append((original, e))


def run(directory: str):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = f"{root}/{file}"
                with open(filepath) as f:
                    source = f.read()
                patches = get_patch(source, filepath)
                test_patch(filepath, patches, source)
    print(f"Passed : {passed}")
    print(f"Failed : {len(failed)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Errors : {len(errored)}")
    print("Skipped")
    for skip in skipped:
        print(ast.unparse(ast.parse(skip)))
    print("Errors")
    for error in errored:
        code = error[0].rstrip()
        print(ast.unparse(ast.parse(code)) + f"\t# {error[1]}")


def main():
    parser = argparse.ArgumentParser(
        prog="accept",
        description="Test the outputs of the patches that would be applied",
        epilog="Copyright 2023 The Galaxy Project (https://galaxyproject.org)\n",
    )

    parser.add_argument("directory", help="the directory to scan", nargs="?")
    args = parser.parse_args()

    if args.directory is None or len(args.directory) == 0:
        run("../../galaxy/lib/galaxy")
    else:
        run(args.directory)


if __name__ == "__main__":
    main()
    sys.exit()
