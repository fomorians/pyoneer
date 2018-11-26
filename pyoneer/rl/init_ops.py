from tensorflow.python.framework import dtypes
from tensorflow.python.framework import ops
from tensorflow.python.ops import init_ops
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import gen_math_ops
from tensorflow.python.ops import math_ops


class SoftplusScale(init_ops.Initializer):
  """Initializer that generates tensors initialized to 1."""

  def __init__(self, scale=1., dtype=dtypes.float32):
    self.dtype = dtypes.as_dtype(dtype)
    self.scale = ops.convert_to_tensor(scale)

  def __call__(self, shape, dtype=None, partition_info=None):
    if dtype is None:
      dtype = self.dtype
    return gen_math_ops.log(gen_math_ops.exp(array_ops.ones(shape) * self.scale) - 1.)

  def get_config(self):
    return {"dtype": self.dtype.name}
