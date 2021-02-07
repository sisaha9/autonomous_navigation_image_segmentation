import os
import cv2
import subprocess

# import some common detectron2 utilities
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.utils.visualizer import Visualizer
from detectron2.data import MetadataCatalog, DatasetCatalog, \
    build_detection_test_loader
from detectron2.data.datasets import register_coco_instances
from detectron2.utils.visualizer import ColorMode
from detectron2.evaluation import COCOEvaluator, inference_on_dataset

from trainer import COCOFormatTrainer

def best_inference(best_model_name, config_dir, model_dir, test_path_images, \
	test_annotations, confidence_threshold, result_metrics_dir, video_img_dir \
	video, framerate):
	#Storing test data
	test_dataset_metadata, test_dataset_dicts = setup_data(test_path_images, \
		test_annotations)
	#Creating config file
	cfg = setup_config(config_dir, model_dir, best_model_name, \
		confidence_threshold)
	#Generating metric saving directory
	os.makedirs(os.path.join(model_dir, "final_test"), exist_ok = True)
	#Creating predictor
	predictor = DefaultPredictor(cfg)
	#Creating evaluator
    evaluator = COCOEvaluator("test_detector", \
    	distributed = False, output_dir=os.path.join(model_dir, "final_test"))
    #Building test loader
    test_loader = build_detection_test_loader(cfg, "test_detector")
    #Loading in train
    trainer = COCOFormatTrainer(cfg)
    #Getting inference results on trainer
    test_results = inference_on_dataset(trainer.model, val_loader, evaluator)
    #Dumping into json file
    with open(os.path.join(result_metrics_dir, 'test_results.json'), 'w') as \
    	outfile:, \
    	json.dump(dict(test_results), outfile)
    #Generating video from predictions
    create_video(video_img_dir, video, test_loader, \
    	test_dataset_metadata, test_dataset_dicts, predictor, framerate)

def setup_data(test_path_images, test_annotations):
    #Register the test datasets into a dictionary
    register_coco_instances("test_detector", {}, test_annotations, \
    	test_path_images)
    #Store test meta data and dictionaries
    test_dataset_metadata = MetadataCatalog.get("test_detector")
    test_dataset_dicts = DatasetCatalog.get("test_detector")
    return test_dataset_metadata, test_dataset_dicts

def setup_config(config_dir, model_dir, model_name, confidence_threshold):
    cfg = get_cfg()
    #Load model parameters
    cfg.merge_from_file(os.path.join(config_dir, model_name + '.yaml'))
    #Load in test data
    cfg.DATASETS.TEST = ("test_detector", )
    #Create output directory to store results
    cfg.OUTPUT_DIR = os.path.join(model_dir, "final_test")
    #Loading weights
    cfg.MODEL.WEIGHTS = os.path.join(os.path.join(model_dir, model_name), \
    	"model_final.pth")
    #Setting confidence threshold
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = confidence_threshold
    #Set config device
    if torch.cuda.is_available():
        print("Using CUDA")
        cfg.MODEL.DEVICE = 'cuda'
    else:
        print("Using CPU")
        cfg.MODEL.DEVICE = 'cpu'
    return cfg

def create_video(video_img_dir, video, test_loader, \
	test_dataset_metadata, test_dataset_dicts, predictor, framerate):
	#Iterating through images in dictionary
	for i, d in enumerate(test_dataset_dicts):    
	    im = cv2.imread(d["file_name"])
	    #Predicting bbox and segmentation
	    outputs = predictor(im)
	    #Generating visualizer for image
	    v = Visualizer(im[:, :, ::-1],
	                   metadata=test_dataset_metadata, 
	                   scale=1, 
	                   instance_mode=ColorMode.IMAGE_BW
	    )
	    #Drawing over the visualizer image
	    v = v.draw_instance_predictions(outputs["instances"].to("cpu"))
	    #Saving image to directory to generate video later
	    cv2.imwrite(os.path.join(video_img_dir, "image{}.jpg".format(i + 1)), \
	    	v.get_image()[:, :, ::-1].astype(np.float))
	#Generate video via ffmpeg
	subprocess.call(["ffmpeg", "-framerate {}".format(framerate), \
		"-pattern_type glob", "-i '{}*.jpg'".format(video_img_dir), \
		"-c:v libx264", "-r 30", "-pix_fmt yuv420p", "-y", video])