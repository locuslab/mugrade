import os
import sys
import numpy as np
import requests
import pickle
import base64
import json
import inspect
import copy
import gzip
import re
import types
import pytest
import importlib
import glob


"""
Note: This use of globals is pretty ugly, but it's unclear to me how to wrap this into 
a class while still being able to use pytest hooks, so this is the hacky solution for now.
"""

_server_url = "https://mugrade.datasciencecourse.org/_/api/"
_values = []
_submission_key = ""
_errors = 0


def init(server):
    """ Initialize global server. """
    global _server_url
    _server_url = server + "/_/api/"


def b64_pickle(obj):
    return base64.b64encode(pickle.dumps(obj)).decode("ASCII")

def start_submission(func_name):
    """ Begin a submisssion to the mugrade server """
    response = requests.post(_server_url + "submission",
                             params = {"user_key": os.environ["MUGRADE_KEY"],
                                       "func_name": func_name})
    if response.status_code != 200:
        raise Exception(f"Error : {response.text}")
    return response.json()["submission_key"]

def submit_test():
    """ Submit a single grader test. """
    global _values, _submission_key, _errors
    response = requests.post(_server_url + "submission_test",
                             params = {"user_key": os.environ["MUGRADE_KEY"],
                                       "submission_key":_submission_key, 
                                       "test_case_index":len(_values)-1,
                                       "output":b64_pickle(_values[-1])})
    print(f"  Test {len(_values)} ", end="")
    if response.status_code != 200:
        print(f"FAILED, with error : {response.text}")
    elif response.json()["status"] != "Passed":
        print(f"FAILED: {response.json()['status']}")
        _errors += 1
    else:
        print(f"PASSED")


def publish(func_name, overwrite=True):
    """ Publish an autograder. """
    global _values, _server_url
    response = requests.post(_server_url + "publish_grader",
                             params = {"user_key": os.environ["MUGRADE_KEY"],
                                       "func_name": func_name,
                                       "target_values": b64_pickle(_values),
                                       "overwrite": overwrite})
    if response.status_code != 200:
        print(f"  Error : {response.text}")
    else:
        print("  " + response.json()["status"])


@pytest.mark.hookwrapper
def pytest_pyfunc_call(pyfuncitem):
    ## prior to test, initialize submission
    global _values, _submission_key, _errors
    _values = []
    _errors = 0
    func_name = pyfuncitem.name[7:]
    if os.environ["MUGRADE_OP"] == "submit":
        _submission_key = start_submission(func_name)
        print(f"\nSubmitting {func_name}...")

    # run test
    output = yield


    # raise excepton if tests failed (previously keep running)
    if os.environ["MUGRADE_OP"] == "submit":
        if _errors > 0:
            pytest.fail(pytrace=False)

    # publish tests
    if os.environ["MUGRADE_OP"] == "publish":
        #print(values)
        publish(func_name)



def submit(result):
    global _values
    _values.append(result)
    if os.environ["MUGRADE_OP"] == "submit":
        submit_test()


## Notebook function dectorator interface
# There are a few oddities here, like using environmental variables, that we
# do to use the same interface for pytest and notebook code, but other than
# this the logic here is fairly straightforward.

class LocalTestContextManager(object):
    def __init__(self):
        self.test_count = 0
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, val, trace):
        print("  Test {} ".format(self.test_count), end="")
        self.test_count += 1
        if exc_type is not None and issubclass(exc_type, AssertionError):
            stack = inspect.stack()
            self.stack = stack
            print("FAILED", stack[1].code_context[0].replace("   with mugrade.test: ","").strip("\n"))
            return True
        elif exc_type is not None:
            return
        else:
            print("PASSED")
            return True
test = LocalTestContextManager()


def import_test_function(func, prefix="test_", frame=None):
    """ Load relevant module and get the test function. """
    test_files = glob.glob("test_*.py")
    test_module = None
    for fname in test_files:
        test_module = importlib.import_module(os.path.splitext(fname)[0])
        test_module = importlib.reload(test_module)
        if hasattr(test_module, prefix + func.__name__):
            break
    if test_module is None or not hasattr(test_module, prefix + func.__name__):
        print("Couldn't find '{}' cases for {}()".format(prefix, func.__name__))
        return
    test_func = getattr(test_module, prefix + func.__name__)
    if frame is not None:
        test_module.__builtins__.update(frame.f_locals)
    test_module.__builtins__[func.__name__] = func
    return test_func


def local_tests(func):
    """ Run the suite of local tests on func """
    test_func = import_test_function(func, prefix="test_", 
                                     frame=inspect.currentframe().f_back)

    print("Running local tests for function {}():".format(func.__name__))
    test.test_count = 1    
    test_func()
    return func


def submit_tests(user_key):
    """ Run the suite of local tests on func """
    def wrap(func):
        test_func = import_test_function(func, prefix="submit_", 
                                         frame=inspect.currentframe().f_back)
        os.environ["MUGRADE_KEY"] = user_key
        os.environ["MUGRADE_OP"] = "submit"

        global _values, _submission_key, _errors
        _values = []
        _errors = 0
        _submission_key = start_submission(func.__name__)

        print("Submitting tests for function {}():".format(func.__name__))
        test_func()
        return func
    return wrap


def publish_tests(user_key, overwrite=False):
    """ Run the suite of local tests on func """
    def wrap(func):
        test_func = import_test_function(func, prefix="submit_", 
                                         frame=inspect.currentframe().f_back)
        os.environ["MUGRADE_KEY"] = user_key
        os.environ["MUGRADE_OP"] = "publish"
        
        global _values
        _values = []

        print("Publishing tests for function {}():".format(func.__name__))
        test_func()
        publish(func.__name__, overwrite=overwrite)

        return func
    return wrap








