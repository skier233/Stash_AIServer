import os
import io
import json
import base64
from uuid import uuid4
from PIL import Image as PILImage
from typing import List, Dict, Tuple

os.environ["DEEPFACE_HOME"] = "."

import pyzipper
import numpy as np
import gradio as gr
from voyager import Index, Space, StorageDataType 

from deepface import DeepFace

THRESHOLD = 0.5

index_arc = Index(Space.Cosine, num_dimensions=512,storage_data_type=StorageDataType.E4M3)
index_arc = index_arc.load('face_arc.voy')

index_facenet = Index(Space.Cosine, num_dimensions=512,storage_data_type=StorageDataType.E4M3)
index_facenet = index_facenet.load('face_facenet.voy')

FACES = json.load(open("faces.json"))

with pyzipper.AESZipFile('persons.zip') as zf:
    password = os.getenv("VISAGE_KEY","83cab153cb8ef767c279d53a2270f842").encode('ascii')
    zf.setpassword(password)
    PERFORMER_DB = json.loads(zf.read('performers.json'))


class EnsembleFaceRecognition:
    def __init__(self, model_weights: Dict[str, float] = None):
        """
        Initialize ensemble face recognition system.
        
        Parameters:
        model_weights: Dictionary mapping model names to their weights
                        If None, all models are weighted equally
        """
        self.model_weights = model_weights or {}
        self.boost_factor = 1.8

    def normalize_distances(self, distances: np.ndarray) -> np.ndarray:
        """Normalize distances to [0,1] range within each model's predictions"""
        min_dist = np.min(distances)
        max_dist = np.max(distances)
        if max_dist == min_dist:
            return np.zeros_like(distances)
        return (distances - min_dist) / (max_dist - min_dist)
    
    def compute_model_confidence(self, 
                                distances: np.ndarray,
                                temperature: float = 0.1) -> np.ndarray:
        """Convert distances to confidence scores for a single model"""
        normalized_distances = self.normalize_distances(distances)
        exp_distances = np.exp(-normalized_distances / temperature)
        return exp_distances / np.sum(exp_distances)
    
    def get_face_embeddings(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """Get face embeddings for each model"""
        return {
            'facenet': DeepFace.represent(img_path=image, detector_backend='skip', model_name='Facenet512', normalization='Facenet2018',align=True)[0]['embedding'],
            'arc': DeepFace.represent(img_path=image, detector_backend='skip', model_name='ArcFace',align=True)[0]['embedding']}
    
    def ensemble_prediction(self,
                            model_predictions: Dict[str, Tuple[List[str], List[float]]],
                            temperature: float = 0.1,
                            min_agreement: float = 0.5) -> List[Tuple[str, float]]:
        """
        Combine predictions from multiple models.
        
        Parameters:
        model_predictions: Dictionary mapping model names to their (distances, names) predictions
        temperature: Temperature parameter for softmax scaling
        min_agreement: Minimum agreement threshold between models
        
        Returns:
        final_predictions: List of (name, confidence) tuples
        """
        # Initialize vote counting
        vote_dict = {}
        confidence_dict = {}
        
        # Process each model's predictions
        for model_name, (names, distances) in model_predictions.items():
            # Get model weight (default to 1.0 if not specified)
            model_weight = self.model_weights.get(model_name, 1.0)
            
            # Compute confidence scores for this model
            confidences = self.compute_model_confidence(np.array(distances), temperature)
            
            # Add weighted votes for top prediction
            top_name = names[0]
            top_confidence = confidences[0]
            
            vote_dict[top_name] = vote_dict.get(top_name, 0) + model_weight
            confidence_dict[top_name] = confidence_dict.get(top_name, [])
            confidence_dict[top_name].append(top_confidence)
        
        # Normalize votes
        total_weight = sum(self.model_weights.values()) if self.model_weights else len(model_predictions)
        
        # Compute final results with minimum agreement check
        final_results = []
        for name, votes in vote_dict.items():
            normalized_votes = votes / total_weight
            # Only include results that meet minimum agreement threshold
            if normalized_votes >= min_agreement:
                avg_confidence = np.mean(confidence_dict[name])
                final_score = normalized_votes * avg_confidence * self.boost_factor
                final_score = min(final_score, 1.0)  # Cap at 1.0
                final_results.append((name, final_score))
        
        # Sort by final score
        final_results.sort(key=lambda x: x[1], reverse=True)
        return final_results


## Prediction functions
def get_performer_info(stash, confidence):
    """Get performer information from the database"""
    performer = PERFORMER_DB.get(stash, [])
    if not performer:
        return None
    
    confidence = int(confidence * 100)
    return {
        'id': stash,
        "name": performer['name'],
        "confidence": confidence,
        'image': performer['image'],
        'country': performer['country'],
        'hits': 1,
        'distance': confidence,
        'performer_url': f"https://stashdb.org/performers/{stash}"
    }

def get_face_predictions(face, ensemble, results):
    """Get predictions for a single face"""
    # Get embeddings for original and flipped images
    embeddings_orig = ensemble.get_face_embeddings(face)
    embeddings_flip = ensemble.get_face_embeddings(np.fliplr(face))

    # Average the embeddings
    facenet = np.mean([embeddings_orig['facenet'], embeddings_flip['facenet']], axis=0)
    arc = np.mean([embeddings_orig['arc'], embeddings_flip['arc']], axis=0)

    # Get predictions from both models
    model_predictions = {
        'facenet': index_facenet.query(facenet, max(results, 50)),
        'arc': index_arc.query(arc, max(results, 50)),
    }

    return ensemble.ensemble_prediction(model_predictions)

def image_search_performer(image, threshold=THRESHOLD, results=3):
    """Search for a performer in an image"""
    image_array = np.array(image)
    ensemble = EnsembleFaceRecognition({"facenet": 1.0, "arc": 1.0})

    try:
        faces = DeepFace.extract_faces(image_array, detector_backend="yolov8")
    except ValueError:
        raise gr.Error("No faces found")

    predictions = get_face_predictions(faces[0]['face'], ensemble, results)
    response = []
    for name, confidence in predictions:
        performer_info = get_performer_info(FACES[name], confidence)
        if performer_info:
            response.append(performer_info)
    return response

def image_search_performers(image, threshold=THRESHOLD, results=3):
    """Search for multiple performers in an image"""
    image_array = np.array(image)
    ensemble = EnsembleFaceRecognition({"facenet": 1.0, "arc": 1.0})

    try:
        faces = DeepFace.extract_faces(image_array, detector_backend="yolov8")
    except ValueError:
        raise gr.Error("No faces found")

    response = []
    for face in faces:
        predictions = get_face_predictions(face['face'], ensemble, results)
        
        # Crop and encode face image
        area = face['facial_area']
        cimage = image.crop((area['x'], area['y'], area['x'] + area['w'], area['y'] + area['h']))
        buf = io.BytesIO()
        cimage.save(buf, format='JPEG')
        im_b64 = base64.b64encode(buf.getvalue()).decode('ascii')

        # Get performer information
        performers = []
        for name, confidence in predictions:
            performer_info = get_performer_info(FACES[name], confidence)
            if performer_info:
                performers.append(performer_info)

        response.append({
            'image': im_b64,
            'confidence': face['confidence'],
            'performers': performers
        })
    return response


def vector_search_performer(vector_json, threshold=20.0, results=3):
    return {'status': 'not implemented'}


def find_faces_in_sprite(image, vtt):
    vtt = base64.b64decode(vtt.replace("data:text/vtt;base64,", ""))
    sprite = PILImage.fromarray(image)

    results = []
    for i, (left, top, right, bottom, time_seconds) in enumerate(getVTToffsets(vtt)):
        cut_frame = sprite.crop((left, top, left + right, top + bottom))
        faces = DeepFace.extract_faces(np.asarray(cut_frame), detector_backend="mediapipe", enforce_detection=False, align=False)
        faces = [face for face in faces if face['confidence'] > 0.6]
        if faces:
            size = faces[0]['facial_area']['w'] * faces[0]['facial_area']['h']
            data = {'id': str(uuid4()), "offset": (left, top, right, bottom), "frame": i, "time": time_seconds, 'size': size}
            results.append(data)

    return results


def getVTToffsets(vtt):
    time_seconds = 0
    left = top = right = bottom = None
    for line in vtt.decode("utf-8").split("\n"):
        line = line.strip()

        if "-->" in line:
            # grab the start time
            # 00:00:00.000 --> 00:00:41.000
            start = line.split("-->")[0].strip().split(":")
            # convert to seconds
            time_seconds = (
                int(start[0]) * 3600
                + int(start[1]) * 60
                + float(start[2])
            )
            left = top = right = bottom = None
        elif "xywh=" in line:
            left, top, right, bottom = line.split("xywh=")[-1].split(",")
            left, top, right, bottom = (
                int(left),
                int(top),
                int(right),
                int(bottom),
            )
        else:
            continue

        if not left:
            continue

        yield left, top, right, bottom, time_seconds


image_search = gr.Interface(
    fn=image_search_performer,
    inputs=[
        gr.Image(),
        gr.Slider(label="threshold",minimum=0.0, maximum=1.0, value=THRESHOLD),
        gr.Slider(label="results", minimum=0, maximum=50, value=3, step=1),
    ],
    outputs=gr.JSON(label=""),
    title="Who is in the photo?",
    description="Upload an image of a person and we'll tell you who it is.",
)

image_search_multiple = gr.Interface(
    fn=image_search_performers,
    inputs=[
        gr.Image(type="pil"),
        gr.Slider(label="threshold",minimum=0.0, maximum=1.0, value=THRESHOLD),
        gr.Slider(label="results", minimum=0, maximum=50, value=3, step=1),
    ],
    outputs=gr.JSON(label=""),
    title="Who is in the photo?",
    description="Upload an image of a person(s) and we'll tell you who it is.",
)

vector_search = gr.Interface(
    fn=vector_search_performer,
    inputs=[
        gr.Textbox(),
        gr.Slider(label="threshold",minimum=0.0, maximum=1.0, value=THRESHOLD),
        gr.Slider(label="results", minimum=0, maximum=50, value=3, step=1),
    ],
    outputs=gr.JSON(label=""),
    description="deprecated",
)

faces_in_sprite = gr.Interface(
    fn=find_faces_in_sprite,
    inputs=[
        gr.Image(),
        gr.Textbox(label="VTT file")
    ],
    outputs=gr.JSON(label=""),
)

gr.TabbedInterface([image_search, image_search_multiple, vector_search, faces_in_sprite]).queue().launch(server_name="0.0.0.0")
