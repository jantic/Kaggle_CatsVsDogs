from __future__ import division, print_function
import numpy as np
from importlib import reload

from common.utils import utils
from common.model.deeplearning.imagerec.pretrained import vgg16
from common.setup.DataSetup import DataSetup
from common.model.deeplearning.imagerec.pretrained.vgg16 import Vgg16
from common.output.csv.KaggleCsvWriter import KaggleCsvWriter
from common.visualization.ImagePerformanceVisualizer import ImagePerformanceVisualizer
from common.model.deeplearning.imagerec.MasterImageClassifier import MasterImageClassifier

run_main_test = False
refine_training = True
image_splitting = False
visualize_performance = True
visualization_class = 'c5'
use_sample = False
number_of_epochs = 3
training_batch_size = 64
validation_batch_size = 64
test_batch_size = 64

reload(utils)
np.set_printoptions(precision=4, linewidth=100)
reload(vgg16)

data_directory="data/"
source_directory= data_directory + "source/"

main_directory = data_directory + "main/"
main_training_set_path = main_directory + "train"
main_validation_set_path = main_directory + "valid"
main_test_set_path = main_directory + "test"
main_cache_path = "./cache/main/"

sample_directory = data_directory + "sample/"
sample_training_set_path = sample_directory + "train"
sample_validation_set_path = sample_directory + "valid"
sample_test_set_path = sample_directory + "test1"
sample_cache_path = "./cache/sample/"

DataSetup.establish_working_data_directory_if_needed(source_directory=source_directory, destination_directory=main_directory,
    destination_sample_directory=sample_directory, image_file_extension='jpg', valid_to_test_ratio=0.1, sample_ratio=0.04,train_augment_factor=5)

training_set_path = sample_training_set_path if use_sample else main_training_set_path
validation_set_path = sample_validation_set_path if use_sample else main_validation_set_path
cache_directory = sample_cache_path if use_sample else main_cache_path

vgg = Vgg16(load_weights_from_cache=True, training_images_path=training_set_path, training_batch_size=training_batch_size, validation_images_path=validation_set_path,
            validation_batch_size=validation_batch_size, cache_directory=cache_directory, num_dense_layers_to_retrain=4, fast_conv_cache_training=True, drop_out=0.5)

if refine_training:
    vgg.refine_training(number_of_epochs)

image_classifier = MasterImageClassifier(vgg)

if run_main_test:
    prediction_summaries = image_classifier.get_all_predictions(main_test_set_path, False, test_batch_size)
    KaggleCsvWriter.write_predictions_for_class_id_to_csv(prediction_summaries, 1)

if visualize_performance:
    test_result_summaries = []
    classes = vgg.get_classes()

    for clazz in classes:
        visualization_test_path = validation_set_path + "/" + clazz
        test_result_summaries.extend(image_classifier.get_all_test_results(visualization_test_path, image_splitting, test_batch_size, clazz))

    ImagePerformanceVisualizer.do_visualizations(test_result_summaries, visualization_class, 5, True, True, True, True)
