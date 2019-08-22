

import sys


PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY3:
    from collections import UserList
    LCLASS = UserList
else:
    LCLASS = list


class TransformsList(LCLASS):
    def __init__(self, _list=None, transforms=None):
        super(TransformsList, self).__init__(_list)
        if transforms is None:
            transforms = []
        self.transforms = transforms
