# Python Log Patching
Replace greedy string formatting in logging statements.

Logging statements should prefer to use _lazy_ string formatting when formatting logging messages.

```python
# Good
log.debug("hello %s", world)

# Bad 
log.debug("hello %s" % world)
log.debug(f"hello {world}")
log.debug("hello {}".format(world))
```

## Rationale

### Speed

String manipulation is expensive in any programming language, and the Python logging framework defers formatting log messages until it can't be avoided [1]. This is standard practice in most logging frameworks; don't perform a bunch of expensive operations if they are only going to be discarded. Formatting the string parameters before passing them to the logging framework bypasses their efforts at efficiency.

While string formatting with `f-strings` is arguably marginally faster that the other string formatting methods, this is only true for logging events that will actually be printed.  Using lazy string formatting is [orders of magnitude](https://gist.github.com/ksuderman/dd1c47d2223f13bed4551615690071ab) faster (4x) if the logging event will be discarded.  For logging events in tight loops and other timing critical code sections that can be substantial.

### Safety

Your debugging statements should **never** introduce exceptions at run time, but they may if you are not checking your format strings yourself. The Python logging framework will catch, log, and handle any exceptions that are raised when formatting the string.

```python
world = None

log.debug(f"hello {world:20}") # this WILL crash your program
log.debug("hello %20s", world) # this will not
```

## Usage

Pass the path to a directory of Python source files to the program as the only positional parameter.  Currently, the program **only** works on directories of files.  Patched files are re-written in place (i.e. overwritten) so be sure to make a backup of your work before patching the logging statements.

You can see the changes that would be made by running the program in *linting* mode.

```
usage: logfix [-h] [-l] [directory ...]

Patch greedy string interpolation in Galaxy.

positional arguments:
  directory   the directory to scan

options:
  -h, --help  show this help message and exit
  -l, --lint  only print the patches that would be applied
```

## Caveats and known limitations

1. Classes that store a logger in the instance (e.g. `self.log`) are ignored. 
1. Import statements are not examined to see if a developer imports the logging module with a different name, or if they make calls to the logging framework with something other than log, logger, or logging.
1. Uses of `str.format` are ignored if:<br/>
   1. the LHS is not a literal string constant, or
   1. keyword arguments are used in the substitution
1. Any trailing comments after the logging statement will be lost.
1. Logging statements that span multiple lines will be rewritten on a sinlge line.
1. Strings with nested quotes are not handled.<br/>
   `"This \"will\" break!"`
1. Simple formatting of strings (i.e. width, and right/left justification) is supported, but anything more complicated will be ignored.  Format strings for floats (e.g. %2.3f) and integers (e.g. %03d) should be handled correctly.

**Note** If a logging statement is encountered that cannot be patched a warning will be printed to `stdout` with the offending statement's line number and name of the file that contained the statement.

## References
1. https://docs.python.org/3/howto/logging.html#optimization