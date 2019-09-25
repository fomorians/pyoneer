from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time
import tensorflow as tf

from pyoneer.rl.targets import reward_ops


class RewardOpsTest(tf.test.TestCase):

    def testNStepDiscountedBootstrapValues(self):
        discount = .99
        n_step = 3
        values = tf.constant(
            [[1.1, 1.2, 1.3, 1.4, 1.5],
             [1.1, 1.2, 1.3, 1.4, 1.5]],
            tf.dtypes.float32)
        seq_lens = 5

        expected_bootstrap_values = tf.stack(
            [(discount ** 3) * values[:, 2],
             (discount ** 3) * values[:, 3],
             (discount ** 3) * values[:, 4],
             (discount ** 2) * values[:, 4],
             (discount ** 1) * values[:, 4]],
            axis=1)

        bootstrap_values = reward_ops.n_step_discounted_bootstrap_values(
            values, n_step, seq_lens, discount)
        self.assertAllClose(bootstrap_values, expected_bootstrap_values)

        expected_bootstrap_values = tf.transpose(expected_bootstrap_values,
                                                 [1, 0])
        bootstrap_values = reward_ops.n_step_discounted_bootstrap_values(
            tf.transpose(values, [1, 0]), n_step, seq_lens, discount,
            time_major=True)
        self.assertAllClose(bootstrap_values, expected_bootstrap_values)

    def testNStepDiscountedReturns(self):
        discount = .99
        n_steps = 3
        rewards = tf.constant([[1.0, 1.1, 1.2, 1.3, 1.4],
                               [1.0, 1.1, 1.2, 1.3, 1.4]], tf.dtypes.float32)
        expected_n_step_returns = tf.stack(
            [rewards[:, 0] + discount * rewards[:, 1] + (discount ** 2 *
                                                         rewards[:, 2]),
             rewards[:, 1] + discount * rewards[:, 2] + (discount ** 2 *
                                                         rewards[:, 3]),
             rewards[:, 2] + discount * rewards[:, 3] + (discount ** 2 *
                                                         rewards[:, 4]),
             rewards[:, 3] + discount * rewards[:, 4],
             rewards[:, 4]], axis=1)
        n_step_returns = reward_ops.n_step_discounted_returns(
            rewards, n_steps, discounts=discount)
        self.assertAllClose(n_step_returns, expected_n_step_returns)

        # Time major.
        expected_n_step_returns = tf.transpose(expected_n_step_returns, [1, 0])
        n_step_returns = reward_ops.n_step_discounted_returns(
            tf.transpose(rewards, [1, 0]), n_steps, discounts=discount,
            time_major=True)
        self.assertAllClose(n_step_returns, expected_n_step_returns)

    def testDiscountedReturns(self):
        discount = .99
        rewards = tf.constant([[1.0, 1.1, 1.2],
                               [1.0, 1.1, 1.2]], tf.dtypes.float32)
        expected_returns = tf.stack(
            [rewards[:, 0] + discount * rewards[:, 1] + (discount ** 2 *
                                                         rewards[:, 2]),
             rewards[:, 1] + discount * rewards[:, 2],
             rewards[:, 2]], axis=1)
        returns = reward_ops.discounted_returns(rewards, discounts=discount)
        self.assertAllClose(returns, expected_returns)

        # Time major.
        expected_returns = tf.transpose(expected_returns, [1, 0])
        returns = reward_ops.discounted_returns(
            tf.transpose(rewards, [1, 0]), discounts=discount, time_major=True)
        self.assertAllClose(returns, expected_returns)

    def testVTraceReturns(self):
        discount = .99
        rewards = tf.constant([[1.0, 1.1, 1.2],
                               [1.0, 1.1, 1.2]], tf.dtypes.float32)
        values = tf.constant([[1.1, 1.2, 1.3],
                              [1.1, 1.2, 1.3]], tf.dtypes.float32)
        probs = tf.constant([[0.2, 0.3, 0.4],
                             [0.2, 0.3, 0.4]], tf.dtypes.float32)
        probs_old = probs
        clip_is = tf.minimum(1., probs / probs_old)
        td = clip_is * ((rewards + discount * tf.concat(
            [values[:, 1:], tf.zeros_like(values[:, :1])], axis=1)) - values)
        expected_returns = tf.stack(
            [((td[:, 0] * clip_is[:, 0]) +
              discount * (clip_is[:, 1] * clip_is[:, 0] * td[:, 1]) +
              discount ** 2 * (clip_is[:, 2] * clip_is[:, 1] * clip_is[:, 0] *
                               td[:, 2])),
             ((td[:, 1] * clip_is[:, 1]) +
              discount * (clip_is[:, 2] * clip_is[:, 1] * td[:, 2])),
             td[:, 2] * clip_is[:, 2]],
            axis=1)
        expected_v_trace_values = expected_returns + values

        v_trace_values = reward_ops.v_trace_returns(
            rewards, values, tf.math.log(probs), tf.math.log(probs_old),
            discounts=discount)

        total_time = 0.
        for _ in range(100):
            start = time.time()
            v_trace_values = reward_ops.v_trace_returns(
                rewards, values, tf.math.log(probs), tf.math.log(probs_old),
                discounts=discount)
            total_time += (time.time() - start)
        total_time /= 100
        print(total_time)

        self.assertAllClose(v_trace_values, expected_v_trace_values)

        # Time major.
        expected_v_trace_values = tf.transpose(expected_v_trace_values, [1, 0])
        v_trace_values = reward_ops.v_trace_returns(
            tf.transpose(rewards, [1, 0]), tf.transpose(values, [1, 0]),
            tf.transpose(tf.math.log(probs), [1, 0]),
            tf.transpose(tf.math.log(probs_old), [1, 0]),
            discounts=discount, time_major=True)
        self.assertAllClose(v_trace_values, expected_v_trace_values)

    def testGeneralizedAdvantageEstimate(self):
        discount = .99
        rewards = tf.constant([[1.0, 1.1, 1.2],
                               [1.0, 1.1, 1.2]], tf.dtypes.float32)
        values = tf.constant([[1.1, 1.2, 1.3],
                              [1.1, 1.2, 1.3]], tf.dtypes.float32)
        lambdas = .975
        td = (rewards + discount * tf.concat([values[:, 1:],
                                              tf.zeros_like(values[:, :1])],
                                             axis=1)) - values
        expected_generalized_td = tf.stack(
            [(td[:, 0] + (discount * lambdas) * (td[:, 1]) +
              (discount * lambdas) ** 2 * td[:, 2]),
             (td[:, 1] + (discount * lambdas) * td[:, 2]),
             td[:, 2]],
            axis=1)

        generalized_td = reward_ops.generalized_advantage_estimate(
            rewards, values, lambdas=lambdas, discounts=discount)
        total_time = 0.
        for _ in range(100):
            start = time.time()
            generalized_td = reward_ops.generalized_advantage_estimate(
                rewards, values, lambdas=lambdas, discounts=discount)
            total_time += (time.time() - start)
        total_time /= 100
        print(total_time)

        self.assertAllClose(generalized_td, expected_generalized_td)

        # Time major.
        expected_generalized_td = tf.transpose(expected_generalized_td, [1, 0])
        generalized_td = reward_ops.generalized_advantage_estimate(
            tf.transpose(rewards, [1, 0]), tf.transpose(values, [1, 0]),
            lambdas=lambdas, discounts=discount, time_major=True)
        self.assertAllClose(generalized_td, expected_generalized_td)


if __name__ == "__main__":
    tf.test.main()
