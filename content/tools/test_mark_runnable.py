"""CODE-RUNNER-01: only a real program gets the reader's "Run karein" button."""

from mark_runnable import runs_cleanly


def test_a_program_that_prints_is_runnable() -> None:
    assert runs_cleanly("x = True\ny = False\nprint(x and y)\n")
    assert runs_cleanly('name = input("Name: ")\nprint("Hi", name)\n')  # input() gets an answer


def test_outlines_fragments_and_unavailable_programs_are_not() -> None:
    assert not runs_cleanly("# Syntax of if-else statement\nif condition:\n    # true\nelse:\n    # false\n")
    assert not runs_cleanly("def add(a, b):\n    return a + b\n")  # prints nothing
    assert not runs_cleanly("import helper\nhelper.greet()\n")  # needs another file
    assert not runs_cleanly("import tkinter as tk\nprint(1)\n")  # no windows in the browser runner
    assert not runs_cleanly("while True:\n    pass\n")  # never ends
