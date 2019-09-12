from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf


class TensorCodec(object):

    def __init__(self, dtypes):
        """Creates a new TensorCodec.

        This creates a codec that encodes structures to strings
            and decodes messages back to the structures.

        Args:
            dtypes: The possibly nested structure containing tensor
                dtypes.
        """
        self._dtypes = dtypes
        self._length_dtype = tf.dtypes.int32
        self._count = len(tf.nest.flatten([self._dtypes]))
        # self._offset = tf.cast(
        #     tf.strings.length(
        #         self._encode(tf.zeros([self._count], self._length_dtype))),
        #     self._length_dtype)

        length_bytes = tf.strings.bytes_split(
            self._encode(tf.zeros([self._count], self._length_dtype)))
        num_length_bytes = tf.shape(length_bytes)[0]
        self._offset = tf.cast(num_length_bytes, self._length_dtype)

    @property
    def dtypes(self):
        return self._dtypes

    @tf.function(autograph=False)
    def _encode(self, tensor):
        return tf.io.serialize_tensor(tensor)

    @tf.function(autograph=False)
    def _decode(self, msg, dtype):
        return tf.io.parse_tensor(msg, dtype)

    @tf.function(autograph=False)
    def encode(self, item):
        """Encode a structure into a packed message.

        Args:
            item: A structure with the same structure as dtypes.

        Returns:
            The encoded message.
        """
        # Ensure the same structure.
        tf.nest.assert_same_structure(item, self.dtypes)

        lengths = []
        structure_msg = []

        def encode_w_lengths(tensor):
            msg = self._encode(tensor)
            structure_msg.append(msg)
            msg_bytes = tf.strings.bytes_split(msg)
            num_msg_bytes = tf.shape(msg_bytes)[0]
            lengths.append(tf.cast(num_msg_bytes, self._length_dtype))
            return msg

        _ = tf.nest.map_structure(encode_w_lengths, item)
        lengths_tensor = tf.stack(lengths, axis=0)
        lengths_msg = self._encode(lengths_tensor)

        buffer_list = tf.concat([lengths_msg[None], structure_msg], axis=0)
        buffer = tf.strings.reduce_join(buffer_list)
        return buffer

    @tf.function(autograph=False)
    def decode(self, item):
        """Decode a packed message that represents a structure.

        Args:
            item: A string representing the encoded message.

        Returns:
            The decoded structure.
        """
        item_bytes = tf.strings.bytes_split(item)
        offset = tf.identity(self._offset)

        # Get the lengths of the items in the encoded string.
        lengths_msg = tf.strings.reduce_join(item_bytes[0:offset])
        lengths = self._decode(lengths_msg, self._length_dtype)
        lengths.set_shape([self._count])

        # Decode the item into the same encoded structure.
        decoded_items = []
        lengths = tf.nest.pack_sequence_as(
            self._dtypes, tf.unstack(lengths, self._count, axis=0))

        lengths = tf.nest.flatten(lengths)
        dtypes = tf.nest.flatten(self._dtypes)
        for length, dtype in zip(lengths, dtypes):
            length.set_shape([])
            item_structure = tf.strings.reduce_join(item_bytes[offset:offset+length])
            offset = offset + length
            decoded_item = self._decode(item_structure, dtype)
            decoded_items.append(decoded_item)

        structure = tf.nest.pack_sequence_as(
            self._dtypes, decoded_items)
        return structure


class Queue(TensorCodec):

    def __init__(self, pipe, key, dtypes):
        """Creates a new Queue.

        This creates a distributed queue datastructure.

        Args:
            pipe: The redis server.
            key: The redis key for the queue.
            dtypes: The possibly nested structure containing tensor
                dtypes.
        """
        super(Queue, self).__init__(dtypes)
        self._pipe = pipe
        self._key = key

    def _enqueue_fn(self, buffer):
        self._pipe.rpush(self._key, buffer.numpy())

    @tf.function(autograph=False)
    def enqueue(self, structure):
        """Enqueue a nested structure.

        Args:
            structure: The nested structure.
        """
        buffer = self.encode(structure)
        with tf.control_dependencies([
                tf.py_function(self._enqueue_fn, (buffer,), ())]):
            return

    def _dequeue_fn(self):
        item = self._pipe.blpop(self._key)
        if item:
            item = item[1]
        return item

    @tf.function(autograph=False)
    def dequeue(self):
        """Dequeue a nested structure.

        Returns:
            The nested structure.
        """
        item = tf.py_function(self._dequeue_fn, (), tf.dtypes.string)
        item = tf.ensure_shape(item, [])
        decoded_item = self.decode(item)
        return decoded_item


class Condition(object):

    def __init__(self, pipe, key):
        """Creates a new Condition.

        This creates a distributed condition datastructure.

        Args:
            pipe: The redis server.
            key: The redis key for the queue.
        """
        self._pipe = pipe
        self._key = key

    def _wait_fn(self, w_id):
        w_id_str = str(w_id.numpy().item())
        self._pipe.rpush(self._key, w_id_str)
        self._pipe.blpop(self._key + w_id_str)

    @tf.function(autograph=False)
    def wait(self, w_id):
        """Block until a producer notifies this id.

        Args:
            w_id: The id to send to the producer.
        """
        with tf.control_dependencies([
                tf.py_function(self._wait_fn, (w_id,), ())]):
            return

    def _notify_fn(self, w_id_):
        self._pipe.rpush(self._key + str(w_id_.numpy().item()), 1)

    @tf.function(autograph=False)
    def notify(self, w_id):
        """Notifies the id."""
        with tf.control_dependencies([
                tf.py_function(self._notify_fn, (w_id,), ())]):
            return

    def _notify_all_fn(self):
        w_ids = []
        while True:
            w_id = self._pipe.lpop(self._key)
            if not w_id:
                break
            w_ids.append(w_id)

        for w_id in w_ids:
            self._pipe.rpush(self._key + str(w_id.decode()), 1)

    @tf.function(autograph=False)
    def notify_all(self):
        """Notifies all active ids."""
        with tf.control_dependencies([
                tf.py_function(self._notify_all_fn, (), ())]):
            return


class Register(TensorCodec):

    def __init__(self, pipe, key, dtypes):
        """Creates a new Register.

        This creates a distributed register datastructure.

        Args:
            pipe: The redis server.
            key: The redis key for the register.
            dtypes: The possibly nested structure containing tensor
                dtypes.
        """
        super(Register, self).__init__(dtypes)
        self._pipe = pipe
        self._key = key

    def _set_fn(self, buffer):
        self._pipe.set(self._key, buffer.numpy())

    @tf.function(autograph=False)
    def set(self, structure):
        """Set the nested structure.

        Args:
            structure: The nested structure.
        """
        buffer = self.encode(structure)
        with tf.control_dependencies([
                tf.py_function(self._set_fn, (buffer,), ())]):
            return

    def _get_fn(self):
        item = self._pipe.get(self._key)
        return item

    @tf.function(autograph=False)
    def get(self):
        """Get the nested structure.

        Returns:
            The nested structure.
        """
        item = tf.py_function(self._get_fn, (), tf.dtypes.string)
        item = tf.ensure_shape(item, [])
        decoded_item = self.decode(item)
        return decoded_item


class MultiEvent(object):

    def __init__(self, pipe, index, num_index, key):
        """Creates a new MultiEvent.

        This creates a distributed register datastructure.

        Args:
            pipe: The redis server.
            index: The corresponding index.
            num_index: The number of indices.
            key: The redis key for the register.
        """
        self._pipe = pipe
        self._index = index
        self._num_index = num_index
        self._key = key

    def _set_fn(self):
        self._pipe.set(self._key + str(self._index), 1)

    @tf.function(autograph=False)
    def set(self):
        """Set the event."""
        with tf.control_dependencies([
                tf.py_function(self._set_fn, (), ())]):
            return

    def _unset_fn(self):
        self._pipe.set(self._key + str(self._index), 0)

    @tf.function(autograph=False)
    def unset(self):
        """Unset the event."""
        with tf.control_dependencies([
                tf.py_function(self._unset_fn, (), ())]):
            return

    def _set_all_fn(self):
        for index in range(self._num_index):
            self._pipe.set(self._key + str(index), 1)

    @tf.function(autograph=False)
    def set_all(self):
        """Set all events."""
        with tf.control_dependencies([
                tf.py_function(self._set_all_fn, (), ())]):
            return

    def _get_fn(self):
        return bool(self._pipe.get(self._key + str(self._index)).decode())

    @tf.function(autograph=False)
    def get(self):
        """Get the nested structure.

        Returns:
            The nested structure.
        """
        with tf.control_dependencies([
                tf.py_function(self._get_fn, (), tf.dtypes.bool)]):
            return