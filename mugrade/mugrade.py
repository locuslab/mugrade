import os
import numpy as np
import requests
import pickle
import base64
import json
import inspect
import copy

import mugrade_test_cases
import importlib

server_url = "https://mugrade.datasciencecourse.org/_/api/"


def objects_equal(value,ref):
    """ Test if two objects are equal according to our autograding rules.
    We have to do this manually so that numpy arrays are compard properly. """

    if type(value) != type(ref):
        return False

    if isinstance(ref, dict):
        if sorted(value.keys()) != sorted(ref.keys()):
            return False
        for k,v in ref.items():
            if not objects_equal(v, value[k]):
                return False
        return True

    elif isinstance(ref, list) or isinstance(ref, tuple):
        if len(value) != len(ref):
            return False
        for a,b in zip(ref, value):
            if not objects_equal(a, b):
                return False
        return True

    elif isinstance(ref, np.ndarray):
        if value.shape != ref.shape:
            return False
        if not np.allclose(ref, value, atol=1e-8):
            return False
        return True

    else:
        return value == ref

def get_lambda_source(f):
    a = inspect.getsource(f).strip()
    return a[a.find("lambda"):].rstrip(",")


def get_test_value(i, func, tests, outputs):
    """Wrapper for getting output of a test, called from several functions"""

    # don't process the same input twice, for speed
    prev_output = False
    for j in range(i):
        if objects_equal(tests[i]["input"], tests[j]["input"]):
            outputs[i] = outputs[j]
            prev_output = True
            break

    if not prev_output:
        if isinstance(tests[i]["input"], tuple):
            outputs[i] = func(*tests[i]["input"])
        else:
            outputs[i] = func(tests[i]["input"])

    # run postprocessing on the output
    if "postprocess" in tests[i]:
        if isinstance(outputs[i], tuple):
            return tests[i]["postprocess"](*outputs[i])
        else:
            return tests[i]["postprocess"](outputs[i])
    else:
        return outputs[i]


def test_local(func):
    """ Run the suite of local tests on func, evaluating each input/output pair """
    importlib.reload(mugrade_test_cases)
    tests = mugrade_test_cases.test_cases[func.__name__]["local_cases"]
    print(f"### Running {len(tests)} local tests")
    outputs = [None]*len(tests)
    for i, test in enumerate(tests):
        print(f"# Running test {i+1}/{len(tests)} ... ", end="")
        value = get_test_value(i, func, tests, outputs)

        if objects_equal(value, test["target"]):
            print ("PASSED")
        else:
            print("FAILED: ")
            print(f"#   For input {test['input']}, ")
            if "postprocess" in test:
                print(f"#     ... postprocessing with function `{get_lambda_source(test['postprocess'])}`,")
            print(f"#     ... expected output {test['target']}")
            print(f"#     ... got output {value}")
            print("#")
    return func

def b64_pickle(obj):
    return base64.b64encode(pickle.dumps(obj)).decode("ASCII")

def b64_unpickle(obj):
    return base64.b64encode(pickle.dumps(obj)).decode("ASCII")

def publish_grader(user_key, overwrite=False):
    """ Run function and post results of cases to the server"""
    def wrap(func):
        importlib.reload(mugrade_test_cases)
        tests = mugrade_test_cases.test_cases[func.__name__]["grader_cases"]
        outputs = [None]*len(tests)
        values = [get_test_value(i, func, tests, outputs) for i in range(len(tests))]

        response = requests.post(server_url + "publish_grader",
             params = {"user_key": user_key,
                "func_name": func.__name__,
                "target_values": b64_pickle(values),
                "overwrite": overwrite})

        if response.status_code != 200:
            print(f"Error : {response.text}")
        else:
            print(response.json()["status"])
        return func
    return wrap



def submit(user_key):
    """ Run function and evaluate test case results """
    def wrap(func):
        importlib.reload(mugrade_test_cases)
        tests = mugrade_test_cases.test_cases[func.__name__]["grader_cases"]
        print(f"### Submitting {len(tests)} grader tests")
        response = requests.post(server_url + "submission",
            params = {"user_key": user_key,
            "func_name": func.__name__,
            "code": inspect.getsource(func)})

        if response.status_code != 200:
            print(f"Error : {response.text}")
            return

        if response.json()["status"] != "Success":
            print(response.json()["status"])
            return
        key = response.json()["submission_key"]

        outputs = [None]*len(tests)
        for i,test in enumerate(tests):
            print(f"# Running test {i+1}/{len(tests)} ... ", end="")
            value = get_test_value(i, func, tests, outputs)
            response = requests.post(server_url + "submission_test",
                params = {"user_key": user_key,
                          "submission_key":key, 
                          "test_case_index":i,
                          "output":b64_pickle(value)})

            if response.status_code != 200:
                print(f"Error : {response.text}")
            else:
                if response.json()["status"] == "Passed":
                    print("PASSED")
                else:
                    print("FAILED")
                    print(f"#   For input {test['input']}")
                    if "postprocess" in test:
                        print(f"#     ... postprocessing with function `{get_lambda_source(test['postprocess'])}`,")
                    print(f"#     {response.json()['status']}")
                    print("#")
        return func
    return wrap



