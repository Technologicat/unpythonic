# -*- coding: utf-8 -*-

from ..ec import setescape, escape, call_ec

def test():
    # "multi-return" using escape continuation
    #
    @setescape()
    def f():
        def g():
            escape("hello from g")  # the argument becomes the return value of f()
            print("not reached")
        g()
        print("not reached either")
    assert f() == "hello from g"

    # lispy call/ec (call-with-escape-continuation)
    #
    @call_ec
    def result(ec):  # effectively, just a code block!
        answer = 42
        ec(answer)  # here this has the same effect as "return answer"...
        print("never reached")
        answer = 23
        return answer
    assert result == 42

    @call_ec
    def result(ec):
        answer = 42
        def inner():
            ec(answer)  # ...but here this directly escapes from the outer def
            print("never reached")
            return 23
        answer = inner()
        print("never reached either")
        return answer
    assert result == 42

    try:
        @call_ec
        def erroneous(ec):
            return ec
        erroneous(42)  # invalid, dynamic extent of the call_ec has ended
    except RuntimeError:
        pass
    else:
        assert False

    # begin() returns the last value. What if we don't want that?
    # (this works because ec() uses the exception mechanism)
    from ..seq import begin
    result = call_ec(lambda ec:
                       begin(print("hi from lambda"),
                             ec(42),  # now we can effectively "return ..." at any point from a lambda!
                             print("never reached")))
    assert result == 42

    # tests with @looped in fploop.py

#    def catching_truth_table():
#        def check(tags, catch_untagged, e):
#            if (tags is None and e.allow_catchall) or \
#               (catch_untagged and e.tag is None):
#                return 2  # unconditional catch
#            if (tags is not None and e.tag is not None): # and e.tag in tags):
#                   return 1  # catch if tags match
#            return 0  # don't catch, pass on
#        _ = None
#        # in this table, we're essentially projecting bool**4 into two dimensions.
#        ps = ((None, False), (None, True),  # @setescape points
#              (set(("tag",)), False), (set(("tag",)), True))
#        es = (Escape(_, None, False),  Escape(_, None, True),  # escape instances
#              Escape(_, "tag", False), Escape(_, "tag", True))
##        # the other reasonable projection:
##        ps = ((None, False), (set(("tag",)), False),
##              (None, True), (set(("tag",)), True))
##        es = (escape(_, None, False), escape(_, "tag", False),
##              escape(_, None, True), escape(_, "tag", True))
#        table = [[check(t, c, e) for e in es] for (t, c) in ps]  # col = e, row = p
#        for row in table:
#            print(row)
#    catching_truth_table()

    print("All tests PASSED")

if __name__ == '__main__':
    test()
