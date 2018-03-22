from bdp_cnn.Lorenz.NN_Lorenz import NN
from keras.layers import Conv2D, Input, Dense, Lambda
from keras.models import Model, Sequential
from keras.callbacks import TensorBoard
import tensorflow as tf
from keras import optimizers
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error
import numpy as np
import matplotlib.pyplot as plt

class CNN(NN):
    """
    Convolutional neural network (CNN) for timeseries prediction with using the Lorenz model.
    """

    def __init__(self, neurons=150, epochs=10, batch=50, filter_size=(5, 1), time_steps=1):
        self.model = None
        self.epochs = epochs
        self.batch = batch
        self.filter = filter_size
        self.neurons = neurons
        self.time_steps = time_steps

        self.init_model(nb_filters=self.neurons, filter_size=self.filter, time_steps=time_steps)

    def init_model(self, nb_filters=100, filter_size=(3, 1), grid_size=(40, 1), time_steps=1):
        """
        Initialisation of CNN model

        Args:
            nb_filters (int): The number of different filters to learn.
            filter_size: The filter size
            grid_size: shape of input
        """

        inputs = Input(shape=(grid_size[0], 1, 1))

        # padding for input grid
        paddings = tf.constant([[0, 0], [2, 2], [0, 0], [0, 0]])
        # execution of reflection padding
        padding_first = Lambda(lambda t: tf.pad(t, paddings, "REFLECT"))(inputs)

        conv_first = Conv2D(filters=nb_filters,
                            kernel_size=filter_size,
                            activation='relu',
                            padding="valid")(padding_first)

        padding_second = Lambda(lambda t: tf.pad(t, paddings, "REFLECT"))(conv_first)

        conv_second = Conv2D(filters=1,
                             kernel_size=filter_size,
                             activation='hard_sigmoid',
                             padding="valid")(padding_second)

        print(inputs)
        print(padding_first)
        print(conv_first)
        print(padding_second)
        print(conv_second)

        # input_shape. tuple does not include the sample axis
        self.model = Model(inputs=inputs, outputs=conv_second)

        opt = optimizers.Adadelta()

        self.model.compile(loss='mae', optimizer=opt, metrics=['mae'])

    def predict(self, x_test):
        """
        Prediction with model

        """
        yhat = self.model.predict(x_test)

        return yhat

    def fit(self, x_train, y_train, x_val, y_val):
        """
        Train the model

        """

        tb_callback = TensorBoard(log_dir='./logs', histogram_freq=0,
                                  write_graph=True, write_images=True)
        callbacks = []
        callbacks.append(tb_callback)

        self.model.fit(x_train, y_train,
                       epochs=self.epochs,
                       batch_size=self.batch,
                       validation_data=(x_val, y_val),
                       shuffle=True,
                       callbacks=callbacks)

    def scale(self, array):
        """
        Scale of input data
        """
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaler = scaler.fit(array)
        return scaler, scaler.transform(array)

    def scale_invert(self, scaler, array):
        """
        Invert application of `scale`
        """
        array = np.reshape(array, (array.shape[0], array.shape[1]))

        array_unscaled = scaler.inverse_transform(array)

        return array_unscaled

    def split_ds(self, array):
        """
        Split some dataset into training, testing and validation.

        Args:
            array: input data

        Returns:
            train, test, val

        """

        train = array[:int(4/6 * array.shape[0]), :, :, :]
        test = array[int(4/6 * array.shape[0]):int(5/6 * array.shape[0]), :, :, :]
        val = array[int(5/6 * array.shape[0]):, :, :, :]

        return train, test, val

    def analysis_scatter(self, ytest, ypred):
        print(ytest.shape)
        print(ypred.shape)

        shape = ypred.shape[0] * ypred.shape[1]

        rmse = np.sqrt(mean_squared_error(ytest.reshape(shape), ypred.reshape(shape)))
        corr = np.corrcoef(ytest.reshape(shape), ypred.reshape(shape))

        m, b = np.polyfit(ytest.reshape(shape), ypred.reshape(shape), 1)
        x = range(-22, 22, 1)
        yreg = np.add(np.multiply(m, x), b)

        print("plotting Results...")

        fig, ax = plt.subplots(figsize=(7, 4))
        fig.suptitle(
            'CNN with {0:d} filter, {1:d} filtersize, {2:d} batchsize,\n {3:d} epochs and {4:d} timesteps: RMSE = {5:5.4f} and CORR = {6:8.6f}'.format(self.neurons,
                                                                                                                  self.filter[0],
                                                                                                                  self.batch,
                                                                                                                  self.epochs,
                                                                                                                  self.time_steps,
                                                                                                                  rmse, corr[0, 1]))
        ax.plot(ytest.reshape(shape), ypred.reshape(shape), lw=0, marker=".", color="blue", alpha=0.05, markeredgewidth=0.0)
        ax.plot(x, yreg, '-', label="Regression", color="red", lw=2)
        ax.legend(loc="upper left")
        ax.grid()
        ax.set_xlabel("Test")
        ax.set_ylabel("Prediction")
        ax.set_xlim(-10, 20)
        ax.set_ylim(-10, 20)
        print("\t saving figure...")
        plt.savefig("CNN_%ineurons_%ifilter_%ibatchsize_%iepochs_%itimesteps.png" %
                    (self.neurons, self.filter[0], self.batch, self.epochs, self.time_steps), dpi=400)


if __name__ == "__main__":
    for neurons in [150, 200, 250]:
        for epochs in [10]:
            cnn = CNN(neurons=neurons, epochs=epochs)

            # data handling
            data = cnn.read_netcdf("100_years_1_member.nc")

            x = data.copy()
            y = np.roll(data.copy(), 1, axis=0)

            xscaler, x = cnn.scale(x)
            yscaler, y = cnn.scale(y)

            x = np.reshape(x, (x.shape[0], x.shape[1], 1, 1))
            y = np.reshape(y, (y.shape[0], y.shape[1], 1, 1))

            xtrain, xtest, xval = cnn.split_ds(x)
            ytrain, ytest, yval = cnn.split_ds(y)

            # train model

            cnn.fit(xtrain, ytrain, xval, yval)

            # prediction
            ypred = cnn.predict(xtest)

            # invert scaling
            ypred = cnn.scale_invert(yscaler, ypred)
            ytest = cnn.scale_invert(yscaler, ytest)

            # performance analysis
            cnn.analysis_scatter(ytest, ypred)

            cnn.model.summary()
            cnn = None
            x = None
            y = None
            xscaler = None
            yscaler = None
            ypred = None