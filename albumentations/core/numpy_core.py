import numpy as np


class TransformsArray(np.ndarray):

    def __new__(cls, input_array, transforms=None):
        obj = np.asarray(input_array).view(cls)
        if transforms is None:
            transforms = []
        obj.transforms = transforms
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.transforms = getattr(obj, 'transforms', None)
