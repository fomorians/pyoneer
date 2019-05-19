from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import math
import tensorflow as tf

from collections import OrderedDict

from tensorflow.python.platform import test

from pyoneer.layers.layers_impl import (
    Normalizer,
    OneHotEncoder,
    AngleEncoder,
    DictFeaturizer,
    ListFeaturizer,
    VecFeaturizer,
)


class LayersTest(test.TestCase):
    def test_normalizer_layer(self):
        layer = Normalizer(loc=0.5, scale=2.0)
        inputs = tf.constant([1.0], dtype=tf.float32)
        outputs = layer(inputs)
        expected = tf.constant([0.25], dtype=tf.float32)
        self.assertAllEqual(outputs, expected)

    def test_one_hot_encoder(self):
        layer = OneHotEncoder(depth=4)
        inputs = tf.constant([3], dtype=tf.int32)
        outputs = layer(inputs)
        expected = tf.constant([[0.0, 0.0, 0.0, 1.0]], dtype=tf.float32)
        self.assertAllEqual(outputs, expected)

    def test_angle_encoder_radians(self):
        layer = AngleEncoder(degrees=False)
        inputs = tf.constant([[math.pi]], dtype=tf.float32)
        outputs = layer(inputs)
        expected = tf.constant([[-1, 0]], dtype=tf.float32)
        self.assertAllClose(outputs, expected)

    def test_angle_encoder_degrees(self):
        layer = AngleEncoder(degrees=True)
        inputs = tf.constant([[180]], dtype=tf.float32)
        outputs = layer(inputs)
        expected = tf.constant([[-1, 0]], dtype=tf.float32)
        self.assertAllClose(outputs, expected)

    def test_dict_featurizer(self):
        layer = DictFeaturizer(
            OrderedDict(
                [
                    ("categorical", OneHotEncoder(depth=4)),
                    ("scalar", Normalizer(loc=0.5, scale=2.0)),
                ]
            )
        )
        features = {
            "categorical": tf.constant([3], dtype=tf.int32),
            "scalar": tf.constant([1.0], dtype=tf.float32),
        }
        outputs = layer(features)
        expected = tf.constant([[0.0, 0.0, 0.0, 1.0, 0.25]], dtype=tf.float32)
        self.assertAllEqual(outputs, expected)

    def test_list_featurizer(self):
        layer = ListFeaturizer(
            [OneHotEncoder(depth=4), Normalizer(loc=0.5, scale=2.0)]
        )
        features = [
            tf.constant([3], dtype=tf.int32),
            tf.constant([1.0], dtype=tf.float32),
        ]
        outputs = layer(features)
        expected = tf.constant([[0.0, 0.0, 0.0, 1.0, 0.25]], dtype=tf.float32)
        self.assertAllEqual(outputs, expected)

    def test_vec_featurizer(self):
        layer = VecFeaturizer(
            [OneHotEncoder(depth=4), Normalizer(loc=0.5, scale=2.0)]
        )
        features = tf.constant([3.0, 1.0], dtype=tf.float32)
        outputs = layer(features)
        expected = tf.constant([[0.0, 0.0, 0.0, 1.0, 0.25]], dtype=tf.float32)
        self.assertAllEqual(outputs, expected)


if __name__ == "__main__":
    test.main()