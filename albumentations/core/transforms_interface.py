from __future__ import absolute_import

import random

import cv2

from albumentations.core.serialization import SerializableMeta
from albumentations.core.six import add_metaclass
from albumentations.core.utils import format_args
from albumentations.core.numpy_core import TransformsArray
from albumentations.core.lists_core import TransformsList

__all__ = ['to_tuple', 'BasicTransform', 'DualTransform', 'ImageOnlyTransform', 'NoOp']


def to_tuple(param, low=None, bias=None):
    """Convert input argument to min-max tuple
    Args:
        param (scalar, tuple or list of 2+ elements): Input value.
            If value is scalar, return value would be (offset - value, offset + value).
            If value is tuple, return value would be value + offset (broadcasted).
        low:  Second element of tuple can be passed as optional argument
        bias: An offset factor added to each element
    """
    if low is not None and bias is not None:
        raise ValueError('Arguments low and bias are mutually exclusive')

    if param is None:
        return param

    if isinstance(param, (int, float)):
        if low is None:
            param = - param, + param
        else:
            param = (low, param) if low < param else (param, low)
    elif isinstance(param, (list, tuple)):
        param = tuple(param)
    else:
        raise ValueError('Argument param must be either scalar (int, float) or tuple')

    if bias is not None:
        return tuple([bias + x for x in param])

    return tuple(param)


@add_metaclass(SerializableMeta)
class BasicTransform(object):
    def __init__(self, always_apply=False, p=0.5):
        self.p = p
        self.always_apply = always_apply
        self._additional_targets = {}

    def __call__(self, force_apply=False, **kwargs):
        if (random.random() < self.p) or self.always_apply or force_apply:
            params = self.get_params()
            params = self.update_params(params, **kwargs)
            if self.targets_as_params:
                targets_as_params = {k: kwargs[k] for k in self.targets_as_params}
                params_dependent_on_targets = self.get_params_dependent_on_targets(targets_as_params)
                params.update(params_dependent_on_targets)
            res = {}
            for key, arg in kwargs.items():
                if arg is not None:
                    target_function = self._get_target_function(key)
                    target_dependencies = {k: kwargs[k] for k in self.target_dependence.get(key, [])}
                    res[key] = target_function(arg, **dict(params, **target_dependencies))
                else:
                    res[key] = None
            return res
        return kwargs

    def __repr__(self):
        state = self.get_base_init_args()
        state.update(self.get_transform_init_args())
        return '{name}({args})'.format(name=self.__class__.__name__, args=format_args(state))

    def _get_target_function(self, key):
        transform_key = key
        if key in self._additional_targets:
            transform_key = self._additional_targets.get(key, None)

        target_function = self.targets.get(transform_key, lambda x, **p: x)
        return target_function

    def keep_memory(self, quant, **params):
        try:
            getattr(quant, 'transforms')
        except AttributeError:
            try:
                quant.transforms = []
            except AttributeError:
                import numpy as np
                if isinstance(quant, np.ndarray):
                    quant = TransformsArray(quant)
                elif isinstance(quant, list):
                    quant = TransformsList(quant)
                else:
                    raise
        quant.transforms.append({'transform': self, 'params': params})

    def apply(self, img, **params):
        raise NotImplementedError

    def _apply(self, quant, *args, **kwargs):
        self.keep_memory(quant, *args, **kwargs)
        return self.apply(quant, *args, **kwargs)

    def get_params(self):
        return {}

    @property
    def targets(self):
        # you must specify targets in subclass
        # for example: ('image', 'mask')
        #              ('image', 'boxes')
        raise NotImplementedError

    def update_params(self, params, **kwargs):
        if hasattr(self, 'interpolation'):
            params['interpolation'] = self.interpolation
        if hasattr(self, 'fill_value'):
            params['fill_value'] = self.fill_value
        params.update(
            {'cols': kwargs['image'].shape[1],
             'rows': kwargs['image'].shape[0]})
        return params

    @property
    def target_dependence(self):
        return {}

    def add_targets(self, additional_targets):
        """Add targets to transform them the same way as one of existing targets
        ex: {'target_image': 'image'}
        ex: {'obj1_mask': 'mask', 'obj2_mask': 'mask'}
        by the way you must have at least one object with key 'image'

        Args:
            additional_targets (dict): keys - new target name, values - old target name. ex: {'image2': 'image'}
        """
        self._additional_targets = additional_targets

    @property
    def targets_as_params(self):
        return []

    def get_params_dependent_on_targets(self, params):
        raise NotImplementedError('Method get_params_dependent_on_targets is not implemented in class ' +
                                  self.__class__.__name__)

    @classmethod
    def get_class_fullname(cls):
        return '{cls.__module__}.{cls.__name__}'.format(cls=cls)

    def get_transform_init_args_names(self):
        raise NotImplementedError(
            'Class {name} is not serializable because the `get_transform_init_args_names` method is not '
            'implemented'.format(
                name=self.get_class_fullname()
            )
        )

    def get_base_init_args(self):
        return {
            'always_apply': self.always_apply,
            'p': self.p,
        }

    def get_transform_init_args(self):
        return {k: getattr(self, k) for k in self.get_transform_init_args_names()}

    def _to_dict(self):
        state = {
            '__class_fullname__': self.get_class_fullname(),
        }
        state.update(self.get_base_init_args())
        state.update(self.get_transform_init_args())
        return state


class DualTransform(BasicTransform):
    """Transform for segmentation task."""

    @property
    def targets(self):
        return {'image': self._apply,
                'mask': self._apply_to_mask,
                'masks': self.apply_to_masks,
                'bboxes': self._apply_to_bboxes,
                'keypoints': self._apply_to_keypoints}

    def _apply_to_bboxes(self, bboxes, **params):
        self.keep_memory(bboxes, **params)
        return self.apply_to_bboxes(bboxes, **params)

    def _apply_to_keypoints(self, keypoints, **params):
        self.keep_memory(keypoints, **params)
        return self.apply_to_keypoints(keypoints, **params)

    def _apply_to_mask(self, mask, **params):
        self.keep_memory(mask, **params)
        return self.apply_to_mask(mask, **params)

    def apply_to_bbox(self, bbox, **params):
        raise NotImplementedError('Method apply_to_bbox is not implemented in class ' + self.__class__.__name__)

    def apply_to_keypoint(self, keypoint, **params):
        raise NotImplementedError('Method apply_to_keypoint is not implemented in class ' + self.__class__.__name__)

    def apply_to_bboxes(self, bboxes, **params):
        bboxes = [list(bbox) for bbox in bboxes]
        return [self.apply_to_bbox(bbox[:4], **params) + bbox[4:] for bbox in bboxes]

    def apply_to_keypoints(self, keypoints, **params):
        keypoints = [list(keypoint) for keypoint in keypoints]
        return [self.apply_to_keypoint(keypoint[:4], **params) + keypoint[4:] for keypoint in keypoints]

    def apply_to_mask(self, img, **params):
        return self.apply(img, **{k: cv2.INTER_NEAREST if k == 'interpolation' else v for k, v in params.items()})

    def apply_to_masks(self, masks, **params):
        return [self.apply_to_mask(mask, **params) for mask in masks]


class ImageOnlyTransform(BasicTransform):
    """Transform applied to image only."""

    @property
    def targets(self):
        return {'image': self.apply}


class NoOp(DualTransform):
    """Does nothing"""

    def apply_to_keypoint(self, keypoint, **params):
        return keypoint

    def apply_to_bbox(self, bbox, **params):
        return bbox

    def apply(self, img, **params):
        return img

    def apply_to_mask(self, img, **params):
        return img
