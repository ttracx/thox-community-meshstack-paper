import sys; sys.path.insert(0, 'exp')
from community_lab import *
def test_whole_request_8b_single_node():
    assert plan_pipeline(MODELS[0], [Node("s",16.0)])["mode"] == "whole-request"
def test_household_trio_27b_unplaceable():
    trio=[Node("a",1.6),Node("b",3.2),Node("c",4.8)]
    assert plan_pipeline(MODELS[4], trio) is None
def test_27b_two_stages_on_4x16():
    pool=[Node(f"c{i}",16.0) for i in range(4)]
    assert plan_pipeline(MODELS[1], pool)["stages"] == 2
def test_foreground_busy_node_never_used():
    pool=[Node("busy",64.0,foreground_busy=True)]
    assert plan_pipeline(MODELS[0], pool) is None
def test_privacy_drills(): assert privacy_drills()["all_pass"]
if __name__ == "__main__":
    for n,f in list(globals().items()):
        if n.startswith("test_"): f(); print("PASS", n)
