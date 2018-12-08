from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from tensorflow.python.framework import dtypes
from tensorflow.python.framework import ops
from tensorflow.python.eager import context
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import gen_array_ops
from tensorflow.python.platform import test

from pyoneer.contrib.interactor import batch_rollout_impl


class MockSpace(object):
    
    def __init__(self, dtype):
        self.dtype = dtype


class CounterEnv(object):

    def __init__(self):
        self.observation_space = MockSpace(dtypes.float32)
        self.action_space = MockSpace(dtypes.float32)
        self._step = 0

    def reset(self, size=None):
        self._step = 1
        if size:
            return array_ops.zeros(size, dtype=self.observation_space.dtype)
        return math_ops.cast(0, dtype=self.observation_space.dtype)

    def step(self, action):
        zero = array_ops.zeros_like(action)
        state = math_ops.cast(zero, self.observation_space.dtype) + self._step
        self._step += 1
        return state, math_ops.cast(zero, dtypes.float32), math_ops.cast(zero, dtypes.bool), {}


class BatchRolloutTest(test.TestCase):

    def testBatchRollout(self):
        with context.eager_mode():
            test_env = CounterEnv()

            def next_action_fn(i, state, action, reward, done, is_initial_state):
                return array_ops.zeros_like(state)

            episodes = 5
            max_steps = 100
            rollout = batch_rollout_impl.batch_rollout(
                test_env,
                next_action_fn,
                initial_state=None,
                initial_action=None,
                initial_reward=None,
                initial_done=None,
                episodes=episodes,
                max_steps=max_steps,
                done_on_max_steps=False)

            expected_states = gen_array_ops.tile(
                array_ops.expand_dims(
                    math_ops.range(max_steps), 0), [episodes, 1])
            expected_actions = array_ops.zeros_like(expected_states)
            expected_rewards = array_ops.zeros_like(expected_states)
            expected_weights = array_ops.ones_like(expected_states)

            self.assertAllClose(rollout.states, expected_states, atol=1e-8)
            self.assertAllClose(rollout.actions, expected_actions, atol=1e-8)
            self.assertAllClose(rollout.rewards, expected_rewards, atol=1e-8)
            self.assertAllClose(rollout.weights, expected_weights, atol=1e-8)

    def testBatchRolloutDoneOnMaxSteps(self):
        with context.eager_mode():
            test_env = CounterEnv()

            def next_action_fn(i, state, action, reward, done, is_initial_state):
                return array_ops.zeros_like(state)

            episodes = 5
            max_steps = 100
            rollout = batch_rollout_impl.batch_rollout(
                test_env,
                next_action_fn,
                initial_state=None,
                initial_action=None,
                initial_reward=None,
                initial_done=None,
                episodes=episodes,
                max_steps=max_steps,
                done_on_max_steps=True)

            expected_states = gen_array_ops.tile(
                array_ops.expand_dims(math_ops.range(max_steps), 0), [episodes, 1])
            expected_actions = array_ops.zeros_like(expected_states)
            expected_rewards = array_ops.zeros_like(expected_states)
            expected_weights = array_ops.concat(
                [array_ops.ones_like(expected_states[..., :-1]),
                array_ops.expand_dims(
                    array_ops.zeros_like(expected_states[..., -1]), -1)], 
                axis=-1)

            self.assertAllClose(rollout.states, expected_states, atol=1e-8)
            self.assertAllClose(rollout.actions, expected_actions, atol=1e-8)
            self.assertAllClose(rollout.rewards, expected_rewards, atol=1e-8)
            self.assertAllClose(rollout.weights, expected_weights, atol=1e-8)


if __name__ == "__main__":
    test.main()