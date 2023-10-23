import unittest

from logfix import *


class PatchTestBase(unittest.TestCase):
    def parse(self, source):
        return ast.parse(source, "__fake__.py").body[0].value

    def assert_patched(self, source, expected):
        patches = get_patch(source, "__fake__.py")
        assert 1 == len(patches)
        assert 1 in patches
        actual = patches[1].render()
        assert actual == expected, f"{actual} != {expected}"

    def assert_unchanged(self, source):
        patches = get_patch(source, "__fake__.py")
        assert 0 == len(patches)


class MethodTests(PatchTestBase):
    """Test functions other than the ``patch`` functions."""

    def test_if_literal_string_is_str_formate(self):
        node = self.parse("'{}'.format(world)")
        assert is_str_format(node)

    def test_if_named_variable_is_str_format(self):
        node = self.parse("msg.format(world)")
        assert is_str_format(node)

    def test_all_logger_names_and_methods(self):
        for name in LOGGER_NAMES:
            for method in LOGGER_METHODS:
                source = f"{name}.{method}('hello world')"
                node = self.parse(source)
                assert is_log_method(node)

    def test_not_a_logger_name(self):
        node = self.parse("foo.info(msg)")
        assert not is_log_method(node)

    def test_not_a_logger_method(self):
        node = self.parse("log.greet(msg)")
        assert not is_log_method(node)


class ModOpTests(PatchTestBase):
    def test_modop(self):
        source = 'log.debug("%s" % a)'
        expected = 'log.debug("%s", a)'
        self.assert_patched(source, expected)

    def test_modop_3(self):
        source = 'log.debug("%s %s %s" % (a, b, c))'
        expected = 'log.debug("%s %s %s", a, b, c)'
        self.assert_patched(source, expected)

    def test_modop_3_functions(self):
        source = 'log.debug("%d %f %s" % (a+b, log(a), foo(bar(x,y))))'
        expected = 'log.debug("%d %f %s", a + b, log(a), foo(bar(x, y)))'
        self.assert_patched(source, expected)

    def test_modop_from_tasks_py(self):
        source = 'log.debug("_cancel_job for job %d: Stopping running task %d" % (job.id, task.id))'
        expected = 'log.debug("_cancel_job for job %d: Stopping running task %d", job.id, task.id)'
        self.assert_patched(source, expected)

    def test_modof_value_formats(self):
        source = 'log.debug("%2.3f %03d %-20s" % (3.14, 1, "hello"))'
        expected = "log.debug(\"%2.3f %03d %-20s\", 3.14, 1, 'hello')"
        self.assert_patched(source, expected)

    def test_preserve_format_string_modop_3(self):
        source = 'log.info("%s %d %f" % (a, b, c))'
        expected = 'log.info("%s %d %f", a, b, c)'
        self.assert_patched(source, expected)

    def test_mod_op_2_named_parameters(self):
        source = "log.error(INSTANCE_ID_INVALID_MESSAGE % raw_value)"
        expected = "log.error(INSTANCE_ID_INVALID_MESSAGE, raw_value)"
        self.assert_patched(source, expected)


class PatchFStringTest(PatchTestBase):
    def test_fstring(self):
        source = 'log.debug(f"hello {world}")'
        expected = 'log.debug("hello %s", world)'
        self.assert_patched(source, expected)

    def test_fstring_with_no_substitutions(self):
        source = 'log.debug(f"hello world")'
        expected = 'log.debug("hello world")'
        self.assert_patched(source, expected)

    def test_fstring_formatted_value_f(self):
        source = 'log.debug(f"pi is {pi:2.3f}")'
        expected = 'log.debug("pi is %2.3f", pi)'
        self.assert_patched(source, expected)

    def test_fstring_formatted_value_d(self):
        source = 'log.debug(f"x is {x:03d}")'
        expected = 'log.debug("x is %03d", x)'
        self.assert_patched(source, expected)

    def test_fstring_formatted_value_s(self):
        source = 'log.debug(f"hello {world:20}")'
        expected = 'log.debug("hello %20s", world)'
        self.assert_patched(source, expected)

    def test_fstring_formatted_value_s_left(self):
        source = 'log.debug(f"hello {world:<20}")'
        expected = 'log.debug("hello %-20s", world)'
        self.assert_patched(source, expected)

    def test_fstring_formatted_value_s_right(self):
        source = 'log.debug(f"hello {world:>20}")'
        expected = 'log.debug("hello %20s", world)'
        self.assert_patched(source, expected)


class PatchIgnoreLazyTest(PatchTestBase):
    """Logging statements that should not be patched"""
    def test_ignore_lazy_1(self):
        source = 'log.debug("%s", a)'
        self.assert_unchanged(source)

    def test_ignore_lazy_3(self):
        source = 'log.debug("%s %s %s", a, b, c)'
        self.assert_unchanged(source)


class PatchStrFormatTest(PatchTestBase):
    """Test patching statements that use ``str.format`` for formatting."""
    def test_preserve_format_string_strformat(self):
        source = 'log.info("%s %d %f".format(a, b, c))'
        expected = 'log.info("%s %d %f", a, b, c)'
        self.assert_patched(source, expected)

    def test_str_format_curly_braces_3(self):
        source = 'log.debug("{} {} {}".format(a, b, c))'
        expected = 'log.debug("%s %s %s", a, b, c)'
        self.assert_patched(source, expected)

    def test_ignore_str_format_with_variable(self):
        source = "log.debug(msg.format(world))"
        self.assert_unchanged(source)

    def test_ignore_str_format_with_keywords(self):
        source = 'log.debug("hello {world}".format(world="world"))'
        self.assert_unchanged(source)

    def test_ignore_str_format_formatted_value(self):
        source = 'log.debug("{:.2f} {:^20}".format(3.1456, world))'
        self.assert_unchanged(source)

    def test_ignore_str_format_formatted_float_value(self):
        source = 'log.debug("{:.2f}".format(3.1456))'
        self.assert_unchanged(source)

    def test_ignore_str_format_formatted_s_value(self):
        source = 'log.debug("{:20}".format(world))'
        self.assert_unchanged(source)

    def test_ignore_str_format_formatted_positionals(self):
        source = 'log.debug("hello {0}".format(world))'
        self.assert_unchanged(source)

    # def test_str_format_3_functions(self):
    #     source = 'log.debug("%d %f %s".format(a+b, log(a), foo(bar(x,y))))'
    #     expected = 'log.debug("%d %f %s", a + b, log(a), foo(bar(x, y)))'
    #     self.assert_patched(source, expected)


class IsLogTest(PatchTestBase):
    def test_all_methods(self):
        for name in LOGGER_NAMES:
            for method in LOGGER_METHODS:
                source = f"{name}.{method}('hello world')"
                node = self.parse(source)
                assert is_log_method(node)

    def test_not_a_logger_name(self):
        node = self.parse("foo.info(msg)")
        assert not is_log_method(node)

    def test_not_a_logger_method(self):
        node = self.parse("log.greet(msg)")
        assert not is_log_method(node)
