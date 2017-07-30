from __future__ import absolute_import
from __future__ import division, print_function

import glob
import os.path
import re

import keras
import numpy as np
from keras.layers.convolutional import MaxPooling2D, ZeroPadding2D, Conv2D
from keras.layers.core import Flatten, Dense, Dropout, Lambda
from keras.models import Sequential
from keras.models import load_model
from keras.optimizers import Adam
from keras.preprocessing import image
from keras.preprocessing.image import DirectoryIterator
from keras.utils.data_utils import get_file

from common.model.deeplearning.imagerec.BatchImagePredictionRequestInfo import BatchImagePredictionRequestInfo
from common.model.deeplearning.imagerec.IImageRecModel import IImageRecModel
from common.model.deeplearning.imagerec.ImagePredictionRequest import ImagePredictionRequest
from common.model.deeplearning.imagerec.ImagePredictionResult import ImagePredictionResult


class Vgg16(IImageRecModel):
    """The VGG 16 Imagenet model"""

    def __init__(self, loadWeightsFromCache: bool, trainingImagesPath: str, training_batch_size: int, validationImagesPath: str, validation_batch_size: int):
        self.TRAINING_BATCH_SIZE = training_batch_size
        self.TRAINING_BATCHES = self.__getBatches(trainingImagesPath, batch_size=training_batch_size)
        self.VALIDATION_BATCHES = self.__getBatches(validationImagesPath, batch_size=validation_batch_size)
        self.VGG_MEAN = np.array([123.68, 116.779, 103.939], dtype=np.float32).reshape((3, 1, 1))
        self.ORIGINAL_MODEL_WEIGHTS_URL = 'http://files.fast.ai/models/'
        self.LOAD_WEIGHTS_FROM_CACHE = loadWeightsFromCache
        self.LATEST_SAVED_WEIGHTS_FILENAME = self.__getLatestSavedWeightsFileName()
        self.LATEST_SAVED_EPOCH = self.__determineEpochNumFromWeighFileName(self.LATEST_SAVED_WEIGHTS_FILENAME)
        self.__create()
        self.__establishClasses()

    def refineTraining(self, numEpochs: int):
        initialEpoch = max(self.LATEST_SAVED_EPOCH, 0) if self.LOAD_WEIGHTS_FROM_CACHE else 0
        self.__fit(self.TRAINING_BATCHES, self.VALIDATION_BATCHES, nb_epoch=numEpochs, initial_epoch=initialEpoch)

    def predict(self, imagePredictionRequests: [ImagePredictionRequest], batch_size: int, details=False) -> [ImagePredictionResult]:
        verbose = 1 if details else 0
        batchRequestInfo = BatchImagePredictionRequestInfo.getInstance(imagePredictionRequests, self.getImageWidth(), self.getImageHeight())
        batchConfidences = self.model.predict(batchRequestInfo.getImageArray(), batch_size=batch_size, verbose=verbose)
        imagePredictionResults = ImagePredictionResult.generateImagePredictionResults(batchConfidences, batchRequestInfo, self.classes)
        return imagePredictionResults

    def getImageWidth(self):
        return 224

    def getImageHeight(self):
        return 224

    def getClasses(self)->list:
        return self.classes

    def __establishClasses(self):
        classes = list(iter(self.TRAINING_BATCHES.class_indices))
        for c in self.TRAINING_BATCHES.class_indices:
            classes[self.TRAINING_BATCHES.class_indices[c]] = c
        self.classes = classes

    def __generateFreshKerasModel(self) -> Sequential:
        model = Sequential()
        model.add(Lambda(self.__vgg_preprocess, input_shape=(3, self.getImageWidth(), self.getImageHeight()),
                         output_shape=(3, self.getImageWidth(), self.getImageHeight())))
        Vgg16.__ConvBlock(model, 2, 64)
        Vgg16.__ConvBlock(model, 2, 128)
        Vgg16.__ConvBlock(model, 3, 256)
        Vgg16.__ConvBlock(model, 3, 512)
        Vgg16.__ConvBlock(model, 3, 512)

        model.add(Flatten())
        Vgg16.__FCBlock(model)
        Vgg16.__FCBlock(model)
        model.add(Dense(1000, activation='softmax'))
        model.load_weights(get_file('vgg16.h5', self.ORIGINAL_MODEL_WEIGHTS_URL + 'vgg16.h5', cache_subdir='models'))
        self.__finetune(model)
        return model

    def __getLatestSavedWeightsFileName(self):
        directory = "./cache/"
        if not os.path.isdir(directory):
            os.mkdir(directory)

        fileNames = glob.glob(directory + "*.h5")
        highestEpoch = 0
        highestEpochFile = ""

        for fileName in fileNames:
            epoch = self.__determineEpochNumFromWeighFileName(fileName)
            if epoch > highestEpoch:
                highestEpoch = epoch
                highestEpochFile = fileName

        return highestEpochFile

    @staticmethod
    def __determineEpochNumFromWeighFileName(fileName):
        matchObj = re.match(r'(.*?weights\.)(\d+)(-)(.*?)(-)(.*?)(\.h5)', fileName, re.M | re.I)
        if matchObj:
            return int(matchObj.group(2)) + 1
        return 0

    @staticmethod
    def __ConvBlock(model: Sequential, layers, filters):
        for i in range(layers):
            model.add(ZeroPadding2D((1, 1)))
            model.add(Conv2D(filters, kernel_size=(3, 3), activation='relu'))
        model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    @staticmethod
    def __FCBlock(model: Sequential):
        model.add(Dense(4096, activation='relu'))
        model.add(Dropout(0.5))

    def __vgg_preprocess(self, x):
        x = x - self.VGG_MEAN
        return x[:, ::-1]  # reverse axis rgb->bgr

    def __canLoadWeightsFromCache(self):
        return self.LOAD_WEIGHTS_FROM_CACHE and self.LATEST_SAVED_EPOCH > 0

    def __create(self):
        if self.__canLoadWeightsFromCache():
            self.model = load_model(self.LATEST_SAVED_WEIGHTS_FILENAME, custom_objects={'__vgg_preprocess': self.__vgg_preprocess})
            self.model.load_weights(self.LATEST_SAVED_WEIGHTS_FILENAME, True)
        else:
            self.model = self.__generateFreshKerasModel()

    def __getBatches(self, path, gen=image.ImageDataGenerator(), shuffle=True, batch_size=8, class_mode='categorical') -> DirectoryIterator:
        return gen.flow_from_directory(path, target_size=(self.getImageWidth(), self.getImageHeight()), color_mode='rgb',
                                       class_mode=class_mode, shuffle=shuffle, batch_size=batch_size)

    def __finetune(self, model: Sequential):
        numClasses = self.TRAINING_BATCHES.num_class
        model.pop()
        for layer in model.layers:
            layer.trainable = False
        model.add(Dense(numClasses, activation='softmax'))
        Vgg16.__compile(model)

    @staticmethod
    def __compile(model: Sequential):
        optimizer = Adam(lr=0.001)
        model.compile(optimizer=optimizer, loss='categorical_crossentropy', metrics=['accuracy'])

    def __fit(self, batches, val_batches, nb_epoch=1, initial_epoch=0):
        # tensorBoard = keras.callbacks.TensorBoard(log_dir='./tblogs', histogram_freq=1, write_graph=True, write_images=True)
        earlyStopping = keras.callbacks.EarlyStopping(monitor='val_loss', min_delta=0.0001, patience=10, verbose=1, mode='auto')
        modelCheckpoint = keras.callbacks.ModelCheckpoint('./cache/weights.{epoch:02d}-{val_loss:.4f}-{val_acc:.4f}.h5', monitor='val_loss', verbose=0, save_best_only=False,
                                                          save_weights_only=False, mode='auto', period=1)
        self.model.fit_generator(batches, steps_per_epoch=int(np.ceil(batches.samples / self.TRAINING_BATCH_SIZE)), epochs=nb_epoch, initial_epoch=initial_epoch,
                                 validation_data=val_batches, validation_steps=int(np.ceil(val_batches.samples / self.TRAINING_BATCH_SIZE)),
                                 callbacks=[earlyStopping, modelCheckpoint])

    def __test(self, path, batch_size=8):
        # noinspection PyTypeChecker
        test_batches = self.__getBatches(path, shuffle=False, batch_size=batch_size, class_mode=None)
        return test_batches, self.model.predict_generator(test_batches, int(np.ceil(test_batches.samples / batch_size)))
