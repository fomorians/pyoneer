from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf


class Stopwatch(object):
    """
    Stopwatch for measuring how long operations take. Great for fast and easy profiling.

    Example:
    >>> x = tf.constant(1.0)
    >>> y = tf.constant(2.0)
    >>> with Stopwatch() as watch:
    >>>    z = x + y
    >>> tf.print(watch.duration)
    >>> # 0.00021505355834960938
    """

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration = None

    def start(self):
        self.start_time = tf.timestamp()

    def stop(self):
        self.end_time = tf.timestamp()
        self.duration = self.end_time - self.start_time

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()


def mock_spec(batch_shapes, specs, initializers=tf.zeros):
    """Batch the creation of tensors by spec.

    Args:
        batch_shapes: Possibly nested structure of `tf.TensorShape`s.
        specs: Possibly nested structure of `tf.TensorSpec`s.
        initializers: Possibly nested structure of functions
            `fn(shape, dtype)`.

    Returns:
        Possibly nested structure of tensors.
    """
    def mock_spec_fn(spec, batch_shape=batch_shapes, initializer=initializers):
        shape = batch_shape.as_list() + spec.shape.as_list()
        return initializer(shape, spec.dtype)

    sequences = [specs]
    batch_shapes_is_nested = tf.nest.is_nested(batch_shapes)
    if batch_shapes_is_nested:
        tf.nest.assert_same_structure(specs, batch_shapes)
        sequences.extend([batch_shapes])

    if tf.nest.is_nested(initializers):
        tf.nest.assert_same_structure(specs, initializers)
        if not batch_shapes_is_nested:
            sequences.extend([tf.nest.map_structure(lambda x: batch_shapes,
                                                    specs)])
        sequences.extend([initializers])

    return tf.nest.map_structure(
        mock_spec_fn, *sequences)