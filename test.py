# -*- coding: utf-8 -*-
def is_int(v):
    try:
        int(v)
        return True
    except:
        pass
    return False

commands = []
v = raw_input("command number: ")
if is_int(v):
    v = int(v)
    for i in range(v):
        commands.append(raw_input("command: "))

    e = raw_input("确认执行吗? [Y/N]: ")
    if e in ["Y","y"]:
        print "OK"


