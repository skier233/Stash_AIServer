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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from deepface import DeepFace

THRESHOLD = 0.5

# Load indices from mounted models directory or local fallback
arc_model_path = '/code/models/face_arc.voy' if os.path.exists('/code/models/face_arc.voy') else 'face_arc.voy'
facenet_model_path = '/code/models/face_facenet.voy' if os.path.exists('/code/models/face_facenet.voy') else 'face_facenet.voy'

print(f"Loading ArcFace model from: {arc_model_path}")
print(f"Loading FaceNet model from: {facenet_model_path}")

index_arc = Index(Space.Cosine, num_dimensions=512,storage_data_type=StorageDataType.E4M3)
index_arc = index_arc.load(arc_model_path)

index_facenet = Index(Space.Cosine, num_dimensions=512,storage_data_type=StorageDataType.E4M3)
index_facenet = index_facenet.load(facenet_model_path)

FACES = json.load(open("faces.json"))

with pyzipper.AESZipFile('persons.zip') as zf:
    password = os.getenv("VISAGE_KEY","83cab153cb8ef767c279d53a2270f842").encode('ascii')
    zf.setpassword(password)
    PERFORMER_DB = json.loads(zf.read('performers.json'))


def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj


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
        'id': str(stash),  # Convert to string
        "name": performer['name'],
        "confidence": int(confidence),  # Ensure int
        'image': performer['image'],
        'country': performer['country'],
        'hits': int(1),  # Ensure int
        'distance': float(confidence),  # Ensure float
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
    
    return convert_numpy_types(response)

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
            'confidence': float(face['confidence']),  # Ensure float
            'performers': performers
        })
    
    return convert_numpy_types(response)


def vector_search_performer(vector_json, threshold=20.0, results=3):
    return {'status': 'not implemented'}


def get_all_person_names():
    """Get all unique person names from FACES data for dropdown"""
    performer_names = []
    for stash_id in FACES:
        performer = PERFORMER_DB.get(stash_id, {})
        if performer and 'name' in performer:
            performer_names.append(performer['name'])
    return sorted(list(set(performer_names)))


def find_closest_faces(selected_person, num_results=10, tolerance=0.3, arc_weight=0.5, facenet_weight=0.5):
    """
    Find the closest faces to a selected person using face vector similarity.
    
    Parameters:
    selected_person (str): Name of the person to find similar faces for
    num_results (int): Maximum number of results to return (1-50)
    tolerance (float): Minimum similarity threshold (0.0-1.0)
    arc_weight (float): Weight for ArcFace model (0.0-1.0)
    facenet_weight (float): Weight for FaceNet model (0.0-1.0)
    
    Returns:
    list: List of similar faces with metadata and similarity scores
    """
    if not selected_person:
        return [{"error": "No person selected"}]
    
    # Find the face ID for the selected person
    target_face_id = None
    target_stash_id = None
    for face_id, stash_id in enumerate(FACES):
        performer = PERFORMER_DB.get(stash_id, {})
        if performer and performer.get('name') == selected_person:
            target_face_id = face_id
            target_stash_id = stash_id
            break
    
    if target_face_id is None:
        return [{"error": f"Person '{selected_person}' not found in database"}]
    
    # Get the target vector from both indices
    try:
        target_vector_arc = index_arc.get_vector(int(target_face_id))
        target_vector_facenet = index_facenet.get_vector(int(target_face_id))
    except Exception as e:
        return [{"error": f"Vector not found for '{selected_person}': {str(e)}"}]
    
    # Query both indices for similar faces - search entire database
    try:
        # Try different search sizes to find the maximum available
        max_search_results = len(FACES)
        for attempt_size in [len(FACES), 50000, 20000, 10000, 5000]:
            try:
                arc_results = index_arc.query(target_vector_arc, min(attempt_size, max_search_results))
                facenet_results = index_facenet.query(target_vector_facenet, min(attempt_size, max_search_results))
                break
            except Exception as e:
                if "Fewer than expected results" in str(e):
                    max_search_results = attempt_size - 1000
                    continue
                else:
                    raise e
        else:
            # If all attempts fail, use a conservative number
            arc_results = index_arc.query(target_vector_arc, 1000)
            facenet_results = index_facenet.query(target_vector_facenet, 1000)
        
        # Process results directly from both indices (bypass ensemble for better results)
        all_results = {}
        
        # Process ArcFace results
        for face_id, distance in zip(arc_results[0], arc_results[1]):
            if face_id == target_face_id:
                continue
            similarity = 1.0 - distance  # Convert distance to similarity
            all_results[face_id] = all_results.get(face_id, [])
            all_results[face_id].append(('arc', similarity))
        
        # Process FaceNet results
        for face_id, distance in zip(facenet_results[0], facenet_results[1]):
            if face_id == target_face_id:
                continue
            similarity = 1.0 - distance  # Convert distance to similarity
            all_results[face_id] = all_results.get(face_id, [])
            all_results[face_id].append(('facenet', similarity))
        
        # Weighted average similarities from both models
        final_results = []
        for face_id, similarities in all_results.items():
            # Calculate weighted average
            weighted_sum = 0
            total_weight = 0
            arc_score = facenet_score = None
            
            for model, sim in similarities:
                if model == 'arc':
                    weighted_sum += sim * arc_weight
                    total_weight += arc_weight
                    arc_score = sim
                elif model == 'facenet':
                    weighted_sum += sim * facenet_weight
                    total_weight += facenet_weight
                    facenet_score = sim
            
            avg_similarity = weighted_sum / total_weight if total_weight > 0 else 0
            
            # Skip if below tolerance
            if avg_similarity < tolerance:
                continue
                
            try:
                performer_info = get_performer_info(FACES[face_id], avg_similarity)
                if performer_info:
                    # Add detailed model scores and weights - CONVERT ALL NUMPY TYPES
                    performer_info.update({
                        'avg_similarity': float(round(avg_similarity, 4)),
                        'arc_similarity': float(round(arc_score, 4)) if arc_score else None,
                        'facenet_similarity': float(round(facenet_score, 4)) if facenet_score else None,
                        'arc_weight': float(arc_weight),
                        'facenet_weight': float(facenet_weight),
                        'face_id': int(face_id)  # Convert numpy.uint64 to int
                    })
                    final_results.append(performer_info)
            except Exception as e:
                final_results.append({"error": f"Error processing face {face_id}: {str(e)}"})
        
        # Sort by confidence (highest first) and return top results
        if final_results:
            final_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            # Add search metadata
            search_metadata = {
                "search_metadata": {
                    "query_person": selected_person,
                    "total_matches": int(len(final_results)),  # Convert to int
                    "tolerance": float(tolerance),  # Convert to float
                    "top_results": int(len(final_results[:num_results]))  # Convert to int
                }
            }
            result = [search_metadata] + final_results[:num_results]
            return convert_numpy_types(result)
        else:
            debug_info = {
                "total_arc_results": int(len(arc_results[0])),
                "total_facenet_results": int(len(facenet_results[0])),
                "target_face_id": int(target_face_id),
                "tolerance": float(tolerance),
                "sample_arc": [(int(x), float(y)) for x, y in list(zip(arc_results[0][:5], arc_results[1][:5]))],
                "sample_facenet": [(int(x), float(y)) for x, y in list(zip(facenet_results[0][:5], facenet_results[1][:5]))]
            }
            return convert_numpy_types([{"error": f"No similar faces found above tolerance {tolerance}", "debug": debug_info}])
    except Exception as e:
        return convert_numpy_types([{"error": f"Error during search: {str(e)}"}])


def compare_two_faces(person1, person2):
    """
    Compare face vectors between two selected persons.
    
    Parameters:
    person1 (str): Name of the first person
    person2 (str): Name of the second person
    
    Returns:
    dict: Comparison results including similarity scores and interpretation
    """
    if not person1 or not person2:
        return {"error": "Please select both persons"}
    
    if person1 == person2:
        return {"similarity": 1.0, "distance": 0.0, "message": "Same person selected"}
    
    # Find face IDs for both persons
    face_id1 = face_id2 = None
    for face_id, stash_id in enumerate(FACES):
        performer = PERFORMER_DB.get(stash_id, {})
        if performer and performer.get('name') == person1:
            face_id1 = face_id
        elif performer and performer.get('name') == person2:
            face_id2 = face_id
    
    if face_id1 is None or face_id2 is None:
        return {"error": "One or both persons not found"}
    
    try:
        # Get vectors for both persons from both indices
        vector1_arc = index_arc.get_vector(int(face_id1))
        vector1_facenet = index_facenet.get_vector(int(face_id1))
        vector2_arc = index_arc.get_vector(int(face_id2))
        vector2_facenet = index_facenet.get_vector(int(face_id2))
        
        # Calculate cosine similarity for both models
        arc_similarity = np.dot(vector1_arc, vector2_arc) / (np.linalg.norm(vector1_arc) * np.linalg.norm(vector2_arc))
        facenet_similarity = np.dot(vector1_facenet, vector2_facenet) / (np.linalg.norm(vector1_facenet) * np.linalg.norm(vector2_facenet))
        
        # Average the similarities
        avg_similarity = (arc_similarity + facenet_similarity) / 2
        
        # Convert to distance (1 - similarity for cosine)
        distance = 1 - avg_similarity
        
        result = {
            "person1": person1,
            "person2": person2,
            "similarity": float(avg_similarity),
            "distance": float(distance),
            "arc_similarity": float(arc_similarity),
            "facenet_similarity": float(facenet_similarity),
            "interpretation": "Very similar" if avg_similarity > 0.8 else "Similar" if avg_similarity > 0.6 else "Somewhat similar" if avg_similarity > 0.4 else "Not very similar"
        }
        return convert_numpy_types(result)
    except Exception as e:
        return {"error": f"Error comparing faces: {str(e)}"}


def batch_compare_one_to_many(target_person, comparison_people_text, tolerance=0.3):
    """
    Compare one person against multiple people in batch.
    
    Parameters:
    target_person (str): Name of the target person to compare against
    comparison_people_text (str): Comma-separated list of people names to compare with
    tolerance (float): Minimum similarity threshold (0.0-1.0)
    
    Returns:
    list: List of comparison results for each person
    """
    if not target_person:
        return [{"error": "Please select a target person"}]
    
    if not comparison_people_text.strip():
        return [{"error": "Please provide comparison people (comma-separated names)"}]
    
    # Parse comparison people from text
    comparison_people = [name.strip() for name in comparison_people_text.split(',') if name.strip()]
    
    if not comparison_people:
        return [{"error": "No valid comparison people found"}]
    
    # Get available person names for validation
    available_names = set(get_all_person_names())
    
    # Validate target person
    if target_person not in available_names:
        return [{"error": f"Target person '{target_person}' not found in database"}]
    
    results = []
    valid_comparisons = []
    invalid_names = []
    
    # Validate comparison people
    for person in comparison_people:
        if person in available_names:
            valid_comparisons.append(person)
        else:
            invalid_names.append(person)
    
    # Add validation summary
    batch_metadata = {
        "batch_metadata": {
            "target_person": target_person,
            "total_requested": len(comparison_people),
            "valid_comparisons": len(valid_comparisons),
            "invalid_names": invalid_names,
            "tolerance": float(tolerance)
        }
    }
    results.append(batch_metadata)
    
    # Perform comparisons
    for person in valid_comparisons:
        comparison_result = compare_two_faces(target_person, person)
        
        # Filter by tolerance if no error
        if "error" not in comparison_result:
            if comparison_result.get("similarity", 0) >= tolerance:
                results.append(comparison_result)
        else:
            results.append(comparison_result)
    
    # Sort by similarity (highest first)
    comparison_results = [r for r in results[1:] if "error" not in r]
    comparison_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
    
    final_result = results[:1] + comparison_results + [r for r in results[1:] if "error" in r]
    return convert_numpy_types(final_result)


def batch_compare_many_to_many(people_group1_text, people_group2_text, tolerance=0.3):
    """
    Compare multiple people from group 1 against multiple people from group 2.
    
    Parameters:
    people_group1_text (str): Comma-separated list of people in group 1
    people_group2_text (str): Comma-separated list of people in group 2
    tolerance (float): Minimum similarity threshold (0.0-1.0)
    
    Returns:
    list: List of all comparison results between the two groups
    """
    if not people_group1_text.strip() or not people_group2_text.strip():
        return [{"error": "Please provide people for both groups (comma-separated names)"}]
    
    # Parse people from both groups
    group1 = [name.strip() for name in people_group1_text.split(',') if name.strip()]
    group2 = [name.strip() for name in people_group2_text.split(',') if name.strip()]
    
    if not group1 or not group2:
        return [{"error": "Both groups must have at least one person"}]
    
    # Get available person names for validation
    available_names = set(get_all_person_names())
    
    # Validate both groups
    valid_group1 = [p for p in group1 if p in available_names]
    valid_group2 = [p for p in group2 if p in available_names]
    invalid_group1 = [p for p in group1 if p not in available_names]
    invalid_group2 = [p for p in group2 if p not in available_names]
    
    results = []
    
    # Add validation summary
    batch_metadata = {
        "batch_metadata": {
            "group1_total": len(group1),
            "group1_valid": len(valid_group1),
            "group1_invalid": invalid_group1,
            "group2_total": len(group2),
            "group2_valid": len(valid_group2),
            "group2_invalid": invalid_group2,
            "total_comparisons": len(valid_group1) * len(valid_group2),
            "tolerance": float(tolerance)
        }
    }
    results.append(batch_metadata)
    
    # Perform all comparisons
    comparison_results = []
    for person1 in valid_group1:
        for person2 in valid_group2:
            if person1 != person2:  # Skip self-comparisons
                comparison_result = compare_two_faces(person1, person2)
                
                # Filter by tolerance if no error
                if "error" not in comparison_result:
                    if comparison_result.get("similarity", 0) >= tolerance:
                        comparison_results.append(comparison_result)
                else:
                    comparison_results.append(comparison_result)
    
    # Sort by similarity (highest first)
    valid_comparisons = [r for r in comparison_results if "error" not in r]
    error_comparisons = [r for r in comparison_results if "error" in r]
    valid_comparisons.sort(key=lambda x: x.get('similarity', 0), reverse=True)
    
    final_result = results + valid_comparisons + error_comparisons
    return convert_numpy_types(final_result)


# FastAPI app for API endpoints
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests
class ImageSearchRequest(BaseModel):
    image_data: str  # Base64 encoded image
    threshold: float = THRESHOLD
    results: int = 3

class FaceComparisonRequest(BaseModel):
    person1: str
    person2: str

class BatchOneToManyRequest(BaseModel):
    target_person: str
    comparison_people: str
    tolerance: float = 0.3

class BatchManyToManyRequest(BaseModel):
    group1_people: str
    group2_people: str
    tolerance: float = 0.3

# API endpoints
@app.post("/api/predict_0")
async def api_image_search(request: ImageSearchRequest):
    """Image search endpoint for single performer"""
    try:
        # Decode base64 image
        image_data = base64.b64decode(request.image_data.split(',')[1] if ',' in request.image_data else request.image_data)
        image = PILImage.open(io.BytesIO(image_data))
        
        result = image_search_performer(image, request.threshold, request.results)
        return {"data": [result]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/predict_1")
async def api_image_search_multiple(request: ImageSearchRequest):
    """Image search endpoint for multiple performers"""
    try:
        # Decode base64 image
        image_data = base64.b64decode(request.image_data.split(',')[1] if ',' in request.image_data else request.image_data)
        image = PILImage.open(io.BytesIO(image_data))
        
        result = image_search_performers(image, request.threshold, request.results)
        return {"data": [result]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/predict_4")
async def api_find_closest_faces():
    """Find closest faces endpoint - expects standard predict format"""
    try:
        from fastapi import Request
        
        async def inner(request: Request):
            body = await request.json()
            data = body.get("data", [])
            
            if len(data) < 5:
                raise HTTPException(status_code=400, detail="Expected 5 parameters: [person_name, num_results, tolerance, arc_weight, facenet_weight]")
            
            selected_person = data[0]
            num_results = int(data[1])
            tolerance = float(data[2])
            arc_weight = float(data[3])
            facenet_weight = float(data[4])
            
            result = find_closest_faces(selected_person, num_results, tolerance, arc_weight, facenet_weight)
            return {"data": [result]}
        
        return await inner(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/compare_faces")
async def api_compare_faces(request: FaceComparisonRequest):
    """Compare two faces endpoint"""
    try:
        result = compare_two_faces(request.person1, request.person2)
        return {"data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/batch_compare_one_to_many")
async def api_batch_compare_one_to_many(request: BatchOneToManyRequest):
    """Batch compare one person to many endpoint"""
    try:
        result = batch_compare_one_to_many(request.target_person, request.comparison_people, request.tolerance)
        return {"data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/batch_compare_many_to_many")
async def api_batch_compare_many_to_many(request: BatchManyToManyRequest):
    """Batch compare many to many endpoint"""
    try:
        result = batch_compare_many_to_many(request.group1_people, request.group2_people, request.tolerance)
        return {"data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/person_names")
async def api_get_person_names():
    """Get all person names endpoint"""
    try:
        names = get_all_person_names()
        return {"data": names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

    return convert_numpy_types(results)


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


def get_closest_faces_interface():
    return gr.Interface(
        fn=find_closest_faces,
        inputs=[
            gr.Dropdown(choices=get_all_person_names(), label="Select Person", allow_custom_value=False, filterable=True),
            gr.Slider(label="Number of Results", minimum=1, maximum=50, value=10, step=1),
            gr.Slider(label="Tolerance (Minimum Similarity)", minimum=0.0, maximum=1.0, value=0.3, step=0.05),
            gr.Slider(label="ArcFace Weight", minimum=0.0, maximum=1.0, value=0.5, step=0.1),
            gr.Slider(label="FaceNet Weight", minimum=0.0, maximum=1.0, value=0.5, step=0.1),
        ],
        outputs=gr.JSON(label="Closest Faces"),
        title="Find Closest Faces",
        description="Select a person to find the most similar faces in the database. Adjust model weights to emphasize different face recognition models.",
    )

def get_face_comparison_interface():
    return gr.Interface(
        fn=compare_two_faces,
        inputs=[
            gr.Dropdown(choices=get_all_person_names(), label="Select First Person", allow_custom_value=False, filterable=True),
            gr.Dropdown(choices=get_all_person_names(), label="Select Second Person", allow_custom_value=False, filterable=True),
        ],
        outputs=gr.JSON(label="Comparison Result"),
        title="Compare Face Vectors",
        description="Select two persons to compare their face vectors and see similarity scores.",
    )

def get_batch_one_to_many_interface():
    return gr.Interface(
        fn=batch_compare_one_to_many,
        inputs=[
            gr.Dropdown(choices=get_all_person_names(), label="Target Person", allow_custom_value=False, filterable=True),
            gr.Textbox(
                label="Comparison People (comma-separated)", 
                placeholder="Enter names separated by commas, e.g., Person A, Person B, Person C",
                lines=3
            ),
            gr.Slider(label="Tolerance (Minimum Similarity)", minimum=0.0, maximum=1.0, value=0.3, step=0.05),
        ],
        outputs=gr.JSON(label="Batch Comparison Results"),
        title="Batch Compare: One vs Many",
        description="Compare one person against multiple people. Enter comparison people as comma-separated names. Results are sorted by similarity (highest first).",
    )

def get_batch_many_to_many_interface():
    return gr.Interface(
        fn=batch_compare_many_to_many,
        inputs=[
            gr.Textbox(
                label="Group 1 People (comma-separated)", 
                placeholder="Enter names separated by commas, e.g., Person A, Person B, Person C",
                lines=3
            ),
            gr.Textbox(
                label="Group 2 People (comma-separated)", 
                placeholder="Enter names separated by commas, e.g., Person X, Person Y, Person Z",
                lines=3
            ),
            gr.Slider(label="Tolerance (Minimum Similarity)", minimum=0.0, maximum=1.0, value=0.3, step=0.05),
        ],
        outputs=gr.JSON(label="Batch Comparison Results"),
        title="Batch Compare: Many vs Many",
        description="Compare multiple people from Group 1 against multiple people from Group 2. Results are sorted by similarity (highest first).",
    )

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

# Launch both FastAPI and Gradio
if __name__ == "__main__":
    import uvicorn
    import threading
    
    # Start FastAPI server in a separate thread
    def start_fastapi():
        uvicorn.run(app, host="0.0.0.0", port=8000)
    
    fastapi_thread = threading.Thread(target=start_fastapi)
    fastapi_thread.daemon = True
    fastapi_thread.start()
    
    # Start Gradio interface
    gr.TabbedInterface([
        image_search, 
        image_search_multiple, 
        vector_search, 
        faces_in_sprite, 
        get_closest_faces_interface(), 
        get_face_comparison_interface(),
        get_batch_one_to_many_interface(),
        get_batch_many_to_many_interface()
    ]).queue().launch(server_name="0.0.0.0", server_port=7860)