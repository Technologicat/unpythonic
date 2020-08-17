# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset, fail

from ..ec import catch, throw, call_ec
from ..seq import begin

def runtests():
    with testset("unpythonic.ec"):
        with testset("multi-return using escape continuation"):
            @catch()
            def f():
                def g():
                    throw("hello from g")  # the argument becomes the return value of f()
                    test[fail, "This line should not be reached."]
                g()
                test[fail, "This line should not be reached."]
            test[f() == "hello from g"]

        with testset("escape from a lambda"):
            # begin() returns the last value. What if we don't want that?
            #
            # This works because ec() uses the exception mechanism,
            # so it interrupts the evaluation of the tuple of args
            # before `begin` is even called.
            result = call_ec(lambda ec:
                               begin(print("hi from lambda"),
                                     ec(42),  # now we can effectively "return ..." at any point from a lambda!
                                     test[fail, "This line should not be reached."]))
            test[result == 42]

        with testset("lispy call/ec (call-with-escape-continuation)"):
            @call_ec
            def result(ec):  # effectively, just a code block!
                answer = 42
                ec(answer)  # here this has the same effect as "return answer"...
                test[fail, "This line should not be reached."]
                answer = 23
                return answer
            test[result == 42]

            @call_ec
            def result(ec):
                answer = 42
                def inner():
                    ec(answer)  # ...but here this directly escapes from the outer def
                    test[fail, "This line should not be reached."]
                    return 23
                answer = inner()
                test[fail, "This line should not be reached."]
                return answer
            test[result == 42]

        with testset("error case"):
            with test_raises(RuntimeError, "should not be able to call an ec instance outside its dynamic extent"):
                @call_ec
                def erroneous(ec):
                    return ec
                erroneous(42)  # invalid, dynamic extent of the call_ec has ended

        # tests with @looped can be found in test_fploop.py

        # def catching_truth_table():
        #     def check(tags, catch_untagged, e):
        #         if (tags is None and e.allow_catchall) or (catch_untagged and e.tag is None):
        #             return 2  # unconditional catch
        #         if (tags is not None and e.tag is not None): # and e.tag in tags):
        #                return 1  # catch if tags match
        #         return 0  # don't catch, pass on
        #     _ = None
        #     # in this table, we're essentially projecting bool**4 into two dimensions.
        #     ps = ((None, False), (None, True),  # @catch points
        #           (set(("tag",)), False), (set(("tag",)), True))
        #     es = (Escape(_, None, False),  Escape(_, None, True),  # `throw` instances
        #           Escape(_, "tag", False), Escape(_, "tag", True))
        #     # # the other reasonable projection:
        #     # ps = ((None, False), (set(("tag",)), False),
        #     #       (None, True), (set(("tag",)), True))
        #     # es = (Escape(_, None, False), Escape(_, "tag", False),
        #     #       Escape(_, None, True), Escape(_, "tag", True))
        #     table = [[check(t, c, e) for e in es] for (t, c) in ps]  # col = e, row = p
        #     for row in table:
        #         print(row)
        # catching_truth_table()

if __name__ == '__main__':
    runtests()
