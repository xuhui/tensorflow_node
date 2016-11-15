import numpy as np
import model.utils as utils
import tensorflow as tf

allowed_activations = ['sigmoid', 'tanh', 'softmax', 'relu', 'linear']
allowed_noises = [None, 'gaussian', 'mask']
allowed_losses = ['rmse', 'cross-entropy']


class StackedAutoEncoder:
    """A deep autoencoder with denoising capability"""

    def assertions(self):
        global allowed_activations, allowed_noises, allowed_losses
        assert self.loss in allowed_losses, 'Incorrect loss given'
        assert 'list' in str(
            type(self.dims)), 'dims must be a list even if there is one layer.'
        assert len(self.epoch) == len(
            self.dims), "No. of epochs must equal to no. of hidden layers"
        assert len(self.activations) == len(
            self.dims), "No. of activations must equal to no. of hidden layers"
        assert all(
            True if x > 0 else False
            for x in self.epoch), "No. of epoch must be atleast 1"
        assert set(self.activations + allowed_activations) == set(
            allowed_activations), "Incorrect activation given."
        assert utils.noise_validator(
            self.noise, allowed_noises), "Incorrect noise given"

    def __init__(self, dims, activations, epoch=1000, noise=None, loss='rmse',
                 lr=0.001, batch_size=100, print_step=50):
        self.print_step = print_step
        self.batch_size = batch_size
        self.lr = lr
        self.loss = loss
        self.activations = activations
        self.noise = noise
        self.epoch = epoch
        self.dims = dims
        self.assertions()
        self.depth = len(dims)
        self.weights, self.biases = {}, {}
        self.iteration = 0

    def add_noise(self, x):
        if self.noise == 'gaussian':
            n = np.random.normal(0, 0.2, (len(x), len(x[0]))).astype(x.dtype)
            return x + n
        if 'mask' in self.noise:
            frac = float(self.noise.split('-')[1])
            temp = np.copy(x)
            for i in temp:
                n = np.random.choice(len(i), int(round(frac * len(i))), replace=False)
                i[n] = 0
            return temp
        if self.noise == 'sp':
            pass

    def fit(self, x):
        for i in range(self.depth):
            print('Layer {0}'.format(i + 1)+' Iteration {0}'.format(self.iteration))
            if self.noise is None:
                x = self.run(data_x=x, activation=self.activations[i],
                             data_x_=x,
                             hidden_dim=self.dims[i], epoch=self.epoch[
                                 i], loss=self.loss,
                             batch_size=self.batch_size, lr=self.lr,
                             print_step=self.print_step)
            else:
                temp = np.copy(x)
                x = self.run(data_x=self.add_noise(temp),
                             activation=self.activations[i], data_x_=x,
                             hidden_dim=self.dims[i],
                             epoch=self.epoch[
                                 i], loss=self.loss,
                             batch_size=self.batch_size,
                             lr=self.lr, print_step=self.print_step)

    def transform(self, data):
        tf.reset_default_graph()
        sess = tf.Session()
        x = tf.constant(data, dtype=tf.float32)
        for w, b, a in zip(self.weights, self.biases, self.activations):
            weight = tf.constant(w, dtype=tf.float32)
            bias = tf.constant(b, dtype=tf.float32)
            layer = tf.matmul(x, weight) + bias
            x = self.activate(layer, a)
        return x.eval(session=sess)

    def fit_transform(self, x):
        self.fit(x)
        return self.transform(x)

    def run(self, data_x, data_x_, hidden_dim, activation, loss, lr,
            print_step, epoch, batch_size=100):

        self.iteration = self.iteration + 1

        tf.reset_default_graph()
        input_dim = len(data_x[0])
        sess = tf.Session()
        
        with tf.name_scope('input'):
            x = tf.placeholder(dtype=tf.float32, shape=[None, input_dim], name='x')
            x_ = tf.placeholder(dtype=tf.float32, shape=[None, input_dim], name='x_')

        if (len(self.weights)==0 and len(self.biases)==0):
            #Generate weights and biases randomly for first run
            with tf.name_scope("encode_weights"):
                encode_weights = tf.Variable(tf.truncated_normal([input_dim, hidden_dim], dtype=tf.float32))
            
            with tf.name_scope("decode_weights"):   
                decode_weights = tf.transpose(encode_weights)

            with tf.name_scope("encode_biases"):
                encode_biases = tf.Variable(tf.truncated_normal([hidden_dim], dtype=tf.float32))

            with tf.name_scope("decode_biases"):
                decode_biases = tf.Variable(tf.truncated_normal([input_dim], dtype=tf.float32))

        else:
            #Retrieve old weights and biases
            with tf.name_scope("encode_weights"):
                encode_weights = tf.Variable(self.weights['encoded'])
            
            with tf.name_scope("decode_weights"):   
                decode_weights = tf.Variable(self.weights['decoded'])

            with tf.name_scope("encode_biases"):
                encode_biases = tf.Variable(self.biases['encoded'])

            with tf.name_scope("decode_biases"):
                decode_biases = tf.Variable(self.biases['decoded'])

        # Add summary ops to collect data
        w_h = tf.histogram_summary("encode_weights", encode_weights)
        b_h = tf.histogram_summary("encode_biases", encode_biases)


        encode = {'weights': encode_weights, 
                  'biases': encode_biases}
    
        decode = {'weights': decode_weights, 
                  'biases': decode_biases}

        with tf.name_scope("encoded"):
            encoded = self.activate(tf.matmul(x, encode['weights']) + encode['biases'], activation)
        
        with tf.name_scope("decoded"):
            decoded = tf.matmul(encoded, decode['weights']) + decode['biases']

        with tf.name_scope("loss"):
            # reconstruction loss
            if loss == 'rmse':
                loss = tf.sqrt(tf.reduce_mean(tf.square(tf.sub(x_, decoded))))
            elif loss == 'cross-entropy':
                loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(decoded, x_))  ### This is not working in it's current form!
                #loss = -tf.reduce_mean(x_ * tf.log(decoded))
            
            tf.scalar_summary("loss", loss)

        with tf.name_scope("train"):
            train_op = tf.train.AdamOptimizer(lr).minimize(loss)

        # Merge all summaries into a single operator
        merged_summary_op = tf.merge_all_summaries()
        
        if (self.iteration == 1):
            summary_writer = tf.train.SummaryWriter(utils.get_summary_dir(), graph=sess.graph)
        else:
            summary_writer = tf.train.SummaryWriter(utils.get_summary_dir())

        sess.run(tf.initialize_all_variables())
        for i in range(epoch):
            b_x, b_x_ = utils.get_batch(data_x, data_x_, batch_size)
            _, summary_str = sess.run([train_op, merged_summary_op], feed_dict={x: b_x, x_: b_x_})

            summary_writer.add_summary(summary_str, self.iteration*epoch + i)
        
        # debug
        # print('Decoded', sess.run(decoded, feed_dict={x: self.data_x_})[0])
        self.weights['encoded'] = sess.run(encode['weights'])
        self.biases['encoded'] = sess.run(encode['biases'])
        self.weights['decoded'] = sess.run(decode['weights'])
        self.biases['decoded'] = sess.run(decode['biases'])

        max_activations_image = utils.get_max_activation_fast(self)
        image_summary_op = tf.image_summary("training_images", tf.reshape(max_activations_image, (1, 280, 280, 1)))
        image_summary_str = sess.run(image_summary_op, feed_dict={x: b_x, x_: b_x_})
        summary_writer.add_summary(image_summary_str, self.iteration)

        return sess.run(encoded, feed_dict={x: data_x_})

    def activate(self, linear, name):
        if name == 'sigmoid':
            return tf.nn.sigmoid(linear, name='encoded')
        elif name == 'softmax':
            return tf.nn.softmax(linear, name='encoded')
        elif name == 'linear':
            return linear
        elif name == 'tanh':
            return tf.nn.tanh(linear, name='encoded')
        elif name == 'relu':
            return tf.nn.relu(linear, name='encoded')
