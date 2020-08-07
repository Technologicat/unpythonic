# -*- coding: utf-8 -*-

from ..assignonce import assignonce

def test():
    with assignonce() as e:
        try:
            e.a = 2
            e.b = 3
        except AttributeError as err:
            print('Test 1 FAILED: {}'.format(err))
            assert False
        else:
            pass

        try:
            e.a = 5  # fail, e.a already defined
        except AttributeError:
            pass
        else:
            print('Test 2 FAILED')
            assert False

        try:
            e.set("a", 42)  # rebind
        except AttributeError as err:
            print('Test 3 FAILED: {}'.format(err))
            assert False
        else:
            pass

        try:
            e.set("c", 3)  # fail, e.c not bound
        except AttributeError:
            pass
        else:
            print('Test 4 FAILED')
            assert False

    print("All tests PASSED")

if __name__ == '__main__':
    test()
