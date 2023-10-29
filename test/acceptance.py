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

things_that_should_be_numbers = """attempts
count
errno
galaxy_job_id
i
id
index
job_id
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


def it_looks_numberic(name: str) -> bool:
    # for x in ['lines', 'id', 'diff', 'count', 'index', 'port', 'size']:
    for x in things_that_should_be_numbers:
        if x in name:
            return True
    return False


class TestHandler(logging.StreamHandler):
    """
    A custom handler we will add to the logger to store the line that was
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
        if it_looks_numberic(self.value):
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
    segments = collect_name(attr)
    name = segments[0]
    # mock[name] = Expando(name)
    update_mock(mock, name)

    # n = 0
    # segment = segments.pop(0)
    # if segment not in mock:
    #     n += 1
    #     mock[segment] = type(f'_T{n}', (TestBaseClass,), dict())
    # obj = mock[segment]
    # while len(segments) > 1:
    #     segment = segments.pop(0)
    #     if not hasattr(obj, segment):
    #         setattr(obj, segment, type(f'_T{n}', (TestBaseClass,), dict()))
    #         n += 1
    #     obj = getattr(obj, segment)
    #
    # segment = segments.pop()
    # if 'id' in segment:
    #     value =  42
    # else:
    #     value = segment
    # setattr(obj, segment, value)

    ## TOO OLD
    # n = 1
    # t = type(f'_T{n}', (object,), data)
    # while len(segments) > 1:
    #     n += 1
    #     segment = segments.pop()
    #     data = dict()
    #     data[segment] = t
    #     t = type(f'_T{n}', (object,), data)
    # key = segments[0]
    # # mock[key] = t
    # if key in mock:
    #     print(f'Adding {t.__name__} to existing {key}')
    #     obj = mock[key]
    #     name = [ x for x in t.__dict__.keys()][0]
    #     setattr(obj, name, t)
    # else:
    #     print(f'Adding object {key}')
    #     mock[key] = t


def get_base_name(node: ast.AST) -> str:
    while hasattr(node, "value") and isinstance(node.value, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
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
    mock["qacct"] = {"exit_status": 42}
    mock["self"] = Expando("self")
    mock["rows"] = list()
    mock["kwargs"] = dict()
    mock["sum"] = lambda x: 42
    # Add variable names used as format string
    mock["INSTANCE_ID_INVALID_MESSAGE"] = "Instance id %s is invalid"
    mock["LOAD FAILURE ERROR"] = "Failure loading %s %s"

    for arg in node.args[1:]:
        if isinstance(arg, ast.Name):
            if it_looks_numberic(arg.id):
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


def test_create_mock():
    # statement = "log.debug('Canceling job %d: Task %s returned an error', tw.job_id, tw.task_id)"
    # statement = "log.debug('Starting queue_job for job %s', job_wrapper.get_id_tag())"
    # statement = 'log.debug("Starting queue_job for job %s", job_wrapper.get_id_tag())'
    # statement = 'log.info("About to execute the following sudo command - [%s]", " ".join(full_command))'
    # statement = 'log.debug("_stop_pid(): %s: PID %d successfully killed with signal %d" % (job_id, pid, sig))'
    # statement = 'log.warning("_stop_pid(): %s: Got errno %s when attempting to signal %d to PID %d: %s"\n% (job_id, errno.errorcode[e.errno], sig, pid, e.strerror))'
    # statement = 'log.error(f"DRMAAUniva: job {job_id} was killed by signal {qacct[\'exit_status\'] - 128}")'
    # statement = 'log.debug("task %s for job %d ended; exit code: %d" % (self.task_id, self.job_id, tool_exit_code if tool_exit_code is not None else -256))'
    # statement = 'log.debug(f"Message {str(trans.user.id)}")'
    # log.debug(f"_copy_hda_to_library_folder: {str((from_hda_id, folder_id, ldda_message))}")
    statement = 'log.info(f"removing all tool tag associations ({str(self.sa_session.scalar(select(func.count(self.app.model.ToolTagAssociation))))})")'
    evaluate(statement)
    # statement = get_patch(statement, 'test.py')[1].statement
    # tree = parse(statement)
    # mock = create_mock(tree)
    #
    # pprint(mock)


passed = 0
failed = list()
errored = list()


def test_patch(filepath: str, patches: dict, source: str):
    global passed, failed, errored
    if len(patches) == 0:
        return
    lines = source.splitlines(keepends=False)
    handler = TestHandler()
    for line_no in sorted(patches):  # .keys().sort():
        patch = patches[line_no]
        original = ""
        for i in range(patch.line, patch.end_line + 1):
            # print(f"{i:04d}: - {lines[i-1]}")
            original += lines[i - 1].lstrip() + "\n"
        # print(f"{patch.line:04d}: + {patch.render()}")
        updated = patch.render().lstrip()
        # print(original)
        # print(updated)
        updated_tree = parse(updated)
        try:
            mock_data = create_mock(updated_tree)
        except:
            print(f"Unable to create mock for {original}", end=None)
            continue
        mock_data["handler"] = handler
        try:
            exec(SETUP + updated, mock_data)
            # print('log line', handler.line)
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
        # return


def run(directory: str):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = f"{root}/{file}"
                with open(filepath) as f:
                    source = f.read()
                patches = get_patch(source, filepath)
                test_patch(filepath, patches, source)
    print(f"Passed: {passed}")
    print(f"Failed: {len(failed)}")
    print(f"Errors: {len(errored)}")
    for error in errored:
        code = error[0].rstrip()
        print(ast.unparse(ast.parse(code)) + f"\t# {error[1]}")
        # print(error[0].rstrip()) #, end=None)
        # print(error[1])
        # print()


def main():
    parser = argparse.ArgumentParser(
        prog="gxlogtest",
        description="Test the outputs of the patches that would be applied",
        epilog="Copyright 2023 The Galaxy Project (https://galaxyproject.org)\n",
    )

    parser.add_argument("directory", help="the directory to scan", nargs="?")
    args = parser.parse_args()
    # if args.directory is None:
    #     parser.print_help()

    if args.directory is None or len(args.directory) == 0:
        run("../../galaxy/lib/galaxy")
    else:
        run(args.directory)


if __name__ == "__main__":
    # test_create_mock()
    main()
    sys.exit()
