from __future__ import division, print_function
import numpy as np
from importlib import reload

from common.utils import utils
from common.model.deeplearning.imagerec.pretrained import vgg16
from common.model.deeplearning.imagerec.pretrained.vgg16 import Vgg16
from common.output.csv.KaggleCsvWriter import KaggleCsvWriter
from common.visualization.ImagePerformanceVisualizer import ImagePerformanceVisualizer
from common.model.deeplearning.imagerec.MasterImageClassifier import MasterImageClassifier
import time

reload(utils)
np.set_printoptions(precision=4, linewidth=100)
reload(vgg16)

data_path = "./data/"
# data_path = "data/sample/"
training_set_path = data_path + "train"
validation_set_path = data_path + "valid"
test_set_path = data_path + "test1"
cache_directory = "./cache/"

vis_test_class = 'dogs'
vis_test_path = validation_set_path + "/" + vis_test_class

number_of_epochs = 6
training_batch_size = 64
validation_batch_size = 64
test_batch_size = 64
vgg = Vgg16(load_weights_from_cache=True, training_images_path=training_set_path, training_batch_size=training_batch_size, validation_images_path=validation_set_path,
            validation_batch_size=validation_batch_size, cache_directory=cache_directory, num_dense_layers_to_retrain=4, fast_conv_cache_training=True, drop_out=0.5)
vgg.refine_training(number_of_epochs)
image_classifier = MasterImageClassifier(vgg)

# pr = cProfile.Profile()
# pr.enable()
start = time.time()

prediction_summaries = image_classifier.get_all_predictions(test_set_path, False, test_batch_size)
KaggleCsvWriter.write_predictions_for_class_id_to_csv(prediction_summaries, 1)
test_result_summaries = image_classifier.get_all_test_results(vis_test_path, False, test_batch_size, vis_test_class)
ImagePerformanceVisualizer.do_visualizations(test_result_summaries, vis_test_class, 5, True, True, True, True)

end = time.time()
print(end - start)
# pr.disable()
# pr.print_stats(sort="cumtime")
