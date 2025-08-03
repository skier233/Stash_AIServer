# =============================================================================
# StashAI Server - Model Evaluators
# =============================================================================
# This module defines evaluation criteria and logic for AI model pass/fail classification

from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Import database models for evaluator configuration
try:
    from database.models import AIModel, AIActionType, EntityType, TestResult
    MODELS_AVAILABLE = True
except ImportError:
    # Fallback to original models if not available
    from database.models import AIActionType, EntityType
    
    class AIModel(str, Enum):
        VISAGE = "visage"
        OPENAI_VISION = "openai_vision"
        CUSTOM = "custom"
    
    class TestResult(str, Enum):
        PASS = "pass"
        FAIL = "fail"
        PENDING = "pending"
        ERROR = "error"
    
    MODELS_AVAILABLE = False

# =============================================================================
# Evaluation Result Classes
# =============================================================================

@dataclass
class EvaluationResult:
    """Result of AI model evaluation"""
    result: TestResult
    score: float  # 0.0 to 1.0
    reason: str
    criteria_met: Dict[str, bool]
    details: Dict[str, Any]

@dataclass
class EvaluationCriteria:
    """Evaluation criteria configuration"""
    min_confidence_threshold: Optional[float] = None
    min_performers_required: Optional[int] = None
    max_processing_time_seconds: Optional[float] = None
    required_tags: Optional[List[str]] = None
    blocked_errors: Optional[List[str]] = None
    min_avg_confidence: Optional[float] = None
    max_failed_attempts: Optional[int] = None
    custom_rules: Optional[Dict[str, Any]] = None

# =============================================================================
# Base Model Evaluator
# =============================================================================

class BaseModelEvaluator:
    """Base class for all AI model evaluators"""
    
    def __init__(self, evaluator_name: str, ai_model: AIModel, action_type: AIActionType, 
                 entity_type: Optional[EntityType] = None):
        self.evaluator_name = evaluator_name
        self.ai_model = ai_model
        self.action_type = action_type
        self.entity_type = entity_type
        self.criteria = EvaluationCriteria()
    
    def set_criteria(self, criteria: EvaluationCriteria):
        """Set evaluation criteria"""
        self.criteria = criteria
    
    def evaluate(self, test_data: Dict[str, Any], response_data: Dict[str, Any], 
                processing_time: Optional[float] = None, error_message: Optional[str] = None) -> EvaluationResult:
        """
        Evaluate AI model test results
        
        Args:
            test_data: Input data sent to AI model
            response_data: Response from AI model
            processing_time: Time taken to process (seconds)
            error_message: Error message if processing failed
            
        Returns:
            EvaluationResult with pass/fail determination and details
        """
        raise NotImplementedError("Subclasses must implement evaluate method")

# =============================================================================
# Visage Face Recognition Evaluator
# =============================================================================

class VisageFaceRecognitionEvaluator(BaseModelEvaluator):
    """Evaluator for Visage face recognition model"""
    
    def __init__(self, entity_type: Optional[EntityType] = None):
        super().__init__(
            evaluator_name="Visage Face Recognition v1.0",
            ai_model=AIModel.VISAGE,
            action_type=AIActionType.FACIAL_RECOGNITION,
            entity_type=entity_type
        )
        
        # Set default criteria for Visage
        self.criteria = EvaluationCriteria(
            min_confidence_threshold=0.7,
            min_performers_required=0,  # 0 means faces are optional
            max_processing_time_seconds=30.0,
            blocked_errors=["network_timeout", "model_error", "invalid_image"],
            min_avg_confidence=0.6
        )
    
    def evaluate(self, test_data: Dict[str, Any], response_data: Dict[str, Any], 
                processing_time: Optional[float] = None, error_message: Optional[str] = None) -> EvaluationResult:
        """Evaluate Visage face recognition results"""
        
        criteria_met = {}
        details = {
            "performers_found": 0,
            "confidence_scores": [],
            "avg_confidence": 0.0,
            "max_confidence": 0.0,
            "processing_time": processing_time or 0.0
        }
        
        # Check for blocking errors first
        if error_message:
            if self.criteria.blocked_errors:
                for blocked_error in self.criteria.blocked_errors:
                    if blocked_error.lower() in error_message.lower():
                        return EvaluationResult(
                            result=TestResult.ERROR,
                            score=0.0,
                            reason=f"Blocked error detected: {blocked_error}",
                            criteria_met=criteria_met,
                            details=details
                        )
            
            # Non-blocking error - still evaluate partial results
            details["error_message"] = error_message
        
        # Extract performance data from response
        performers_found = 0
        confidence_scores = []
        
        if isinstance(response_data, dict):
            # Check different response formats
            if "performers" in response_data and isinstance(response_data["performers"], list):
                performers = response_data["performers"]
                performers_found = len([p for p in performers if isinstance(p, dict) and p.get("confidence", 0) > 0])
                confidence_scores = [p.get("confidence", 0) for p in performers if isinstance(p, dict) and p.get("confidence", 0) > 0]
                
            elif "faces" in response_data and isinstance(response_data["faces"], list):
                faces = response_data["faces"]
                performers_found = len([f for f in faces if isinstance(f, dict) and f.get("confidence", 0) > 0])
                confidence_scores = [f.get("confidence", 0) for f in faces if isinstance(f, dict) and f.get("confidence", 0) > 0]
                
            elif "success" in response_data and response_data.get("success"):
                # Simple success response - assume 1 performer found
                performers_found = 1
                confidence_scores = [response_data.get("confidence", 0.8)]  # Default confidence if not specified
        
        # Update details
        details["performers_found"] = performers_found
        details["confidence_scores"] = confidence_scores
        details["max_confidence"] = max(confidence_scores) if confidence_scores else 0.0
        details["avg_confidence"] = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        # Evaluate criteria
        score = 0.0
        total_criteria = 0
        reasons = []
        
        # 1. Check minimum confidence threshold
        if self.criteria.min_confidence_threshold is not None:
            total_criteria += 1
            valid_confidences = [c for c in confidence_scores if c >= self.criteria.min_confidence_threshold]
            if valid_confidences:
                criteria_met["min_confidence_threshold"] = True
                score += 1.0
                reasons.append(f"Found {len(valid_confidences)} faces above {self.criteria.min_confidence_threshold} confidence")
            else:
                criteria_met["min_confidence_threshold"] = False
                reasons.append(f"No faces found above {self.criteria.min_confidence_threshold} confidence threshold")
        
        # 2. Check minimum performers required
        if self.criteria.min_performers_required is not None:
            total_criteria += 1
            if performers_found >= self.criteria.min_performers_required:
                criteria_met["min_performers_required"] = True
                score += 1.0
                reasons.append(f"Found {performers_found} performers (required: {self.criteria.min_performers_required})")
            else:
                criteria_met["min_performers_required"] = False
                reasons.append(f"Only found {performers_found} performers (required: {self.criteria.min_performers_required})")
        
        # 3. Check processing time
        if self.criteria.max_processing_time_seconds is not None and processing_time is not None:
            total_criteria += 1
            if processing_time <= self.criteria.max_processing_time_seconds:
                criteria_met["max_processing_time"] = True
                score += 1.0
                reasons.append(f"Processing completed in {processing_time:.2f}s (limit: {self.criteria.max_processing_time_seconds}s)")
            else:
                criteria_met["max_processing_time"] = False
                reasons.append(f"Processing took {processing_time:.2f}s (limit: {self.criteria.max_processing_time_seconds}s)")
        
        # 4. Check average confidence
        if self.criteria.min_avg_confidence is not None and confidence_scores:
            total_criteria += 1
            avg_conf = details["avg_confidence"]
            if avg_conf >= self.criteria.min_avg_confidence:
                criteria_met["min_avg_confidence"] = True
                score += 1.0
                reasons.append(f"Average confidence {avg_conf:.3f} meets minimum {self.criteria.min_avg_confidence}")
            else:
                criteria_met["min_avg_confidence"] = False
                reasons.append(f"Average confidence {avg_conf:.3f} below minimum {self.criteria.min_avg_confidence}")
        
        # Calculate final score (percentage of criteria met)
        final_score = score / total_criteria if total_criteria > 0 else 1.0
        
        # Determine pass/fail
        # Pass if all mandatory criteria are met OR if we found valid results with good confidence
        result = TestResult.PASS
        
        if error_message and not response_data:
            result = TestResult.ERROR
        elif final_score < 0.5:  # Less than 50% of criteria met
            result = TestResult.FAIL
        elif performers_found == 0 and self.criteria.min_performers_required and self.criteria.min_performers_required > 0:
            result = TestResult.FAIL
        else:
            result = TestResult.PASS
        
        reason = "; ".join(reasons) if reasons else "Standard evaluation completed"
        
        return EvaluationResult(
            result=result,
            score=final_score,
            reason=reason,
            criteria_met=criteria_met,
            details=details
        )

# =============================================================================
# Gallery Identification Evaluator
# =============================================================================

class VisageGalleryEvaluator(BaseModelEvaluator):
    """Evaluator for Visage gallery identification"""
    
    def __init__(self):
        super().__init__(
            evaluator_name="Visage Gallery Processing v1.0",
            ai_model=AIModel.VISAGE,
            action_type=AIActionType.GALLERY_IDENTIFICATION,
            entity_type=EntityType.GALLERY
        )
        
        # Set default criteria for gallery processing
        self.criteria = EvaluationCriteria(
            min_confidence_threshold=0.6,
            min_performers_required=0,  # Galleries may have no faces
            max_processing_time_seconds=300.0,  # 5 minutes for galleries
            blocked_errors=["network_timeout", "model_error"],
            min_avg_confidence=0.5,
            max_failed_attempts=3
        )
    
    def evaluate(self, test_data: Dict[str, Any], response_data: Dict[str, Any], 
                processing_time: Optional[float] = None, error_message: Optional[str] = None) -> EvaluationResult:
        """Evaluate Visage gallery processing results"""
        
        criteria_met = {}
        details = {
            "total_images": 0,
            "images_processed": 0,
            "images_with_faces": 0,
            "total_performers_found": 0,
            "avg_confidence": 0.0,
            "processing_time": processing_time or 0.0,
            "success_rate": 0.0
        }
        
        # Extract gallery processing data
        total_images = 0
        images_processed = 0
        images_with_faces = 0
        total_performers = 0
        all_confidences = []
        
        if isinstance(test_data, dict) and "images" in test_data:
            total_images = len(test_data["images"])
            details["total_images"] = total_images
        
        if isinstance(response_data, dict):
            if "results" in response_data and isinstance(response_data["results"], list):
                # Gallery processing results format
                results = response_data["results"]
                images_processed = len(results)
                
                for result in results:
                    if isinstance(result, dict):
                        if "performers" in result and isinstance(result["performers"], list):
                            performers = result["performers"]
                            if performers:
                                images_with_faces += 1
                                total_performers += len(performers)
                                # Extract confidence scores
                                for p in performers:
                                    if isinstance(p, dict) and "confidence" in p:
                                        all_confidences.append(p["confidence"])
                        elif "faces" in result and isinstance(result["faces"], list):
                            faces = result["faces"]
                            if faces:
                                images_with_faces += 1
                                total_performers += len(faces)
                                for f in faces:
                                    if isinstance(f, dict) and "confidence" in f:
                                        all_confidences.append(f["confidence"])
            
            elif "performers" in response_data:
                # Single result format
                images_processed = 1
                if isinstance(response_data["performers"], list) and response_data["performers"]:
                    images_with_faces = 1
                    total_performers = len(response_data["performers"])
                    all_confidences = [p.get("confidence", 0) for p in response_data["performers"] 
                                     if isinstance(p, dict) and "confidence" in p]
        
        # Update details
        details["images_processed"] = images_processed
        details["images_with_faces"] = images_with_faces
        details["total_performers_found"] = total_performers
        details["avg_confidence"] = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        details["success_rate"] = (images_processed / total_images) if total_images > 0 else 0.0
        
        # Evaluate criteria
        score = 0.0
        total_criteria = 0
        reasons = []
        
        # 1. Check processing completion rate
        total_criteria += 1
        completion_rate = details["success_rate"]
        if completion_rate >= 0.8:  # 80% of images processed
            criteria_met["completion_rate"] = True
            score += 1.0
            reasons.append(f"Processed {images_processed}/{total_images} images ({completion_rate*100:.1f}%)")
        else:
            criteria_met["completion_rate"] = False
            reasons.append(f"Only processed {images_processed}/{total_images} images ({completion_rate*100:.1f}%)")
        
        # 2. Check confidence scores for found faces
        if self.criteria.min_confidence_threshold is not None and all_confidences:
            total_criteria += 1
            high_confidence_faces = [c for c in all_confidences if c >= self.criteria.min_confidence_threshold]
            if high_confidence_faces:
                criteria_met["min_confidence_threshold"] = True
                score += 1.0
                reasons.append(f"Found {len(high_confidence_faces)} high-confidence faces (>{self.criteria.min_confidence_threshold})")
            else:
                criteria_met["min_confidence_threshold"] = False
                reasons.append(f"No faces found above {self.criteria.min_confidence_threshold} confidence")
        
        # 3. Check processing time
        if self.criteria.max_processing_time_seconds is not None and processing_time is not None:
            total_criteria += 1
            if processing_time <= self.criteria.max_processing_time_seconds:
                criteria_met["max_processing_time"] = True
                score += 1.0
                reasons.append(f"Completed in {processing_time:.1f}s (limit: {self.criteria.max_processing_time_seconds}s)")
            else:
                criteria_met["max_processing_time"] = False
                reasons.append(f"Took {processing_time:.1f}s (limit: {self.criteria.max_processing_time_seconds}s)")
        
        # 4. Check for errors
        total_criteria += 1
        if not error_message:
            criteria_met["no_errors"] = True
            score += 1.0
            reasons.append("No processing errors")
        else:
            criteria_met["no_errors"] = False
            reasons.append(f"Processing error: {error_message[:100]}")
        
        # Calculate final score
        final_score = score / total_criteria if total_criteria > 0 else 0.0
        
        # Determine result
        if error_message and images_processed == 0:
            result = TestResult.ERROR
        elif final_score >= 0.75:  # 75% of criteria met
            result = TestResult.PASS
        elif final_score >= 0.5:  # Partial success
            result = TestResult.PASS  # Still consider partial success as pass for galleries
        else:
            result = TestResult.FAIL
        
        reason = "; ".join(reasons) if reasons else "Gallery evaluation completed"
        
        return EvaluationResult(
            result=result,
            score=final_score,
            reason=reason,
            criteria_met=criteria_met,
            details=details
        )

# =============================================================================
# Scene Identification Evaluator
# =============================================================================

class VisageSceneEvaluator(BaseModelEvaluator):
    """Evaluator for Visage scene identification"""
    
    def __init__(self):
        super().__init__(
            evaluator_name="Visage Scene Processing v1.0",
            ai_model=AIModel.VISAGE,
            action_type=AIActionType.SCENE_IDENTIFICATION,
            entity_type=EntityType.SCENE
        )
        
        # Set default criteria for scene processing
        self.criteria = EvaluationCriteria(
            min_confidence_threshold=0.65,
            min_performers_required=0,  # Scenes may have no identifiable faces
            max_processing_time_seconds=120.0,  # 2 minutes for scenes
            blocked_errors=["network_timeout", "model_error", "video_decode_error"],
            min_avg_confidence=0.55
        )
    
    def evaluate(self, test_data: Dict[str, Any], response_data: Dict[str, Any], 
                processing_time: Optional[float] = None, error_message: Optional[str] = None) -> EvaluationResult:
        """Evaluate Visage scene processing results"""
        
        # Scene evaluation is similar to single image but may have additional context
        # Reuse the face recognition logic but adjust criteria
        face_evaluator = VisageFaceRecognitionEvaluator()
        face_evaluator.criteria = self.criteria  # Use scene-specific criteria
        
        result = face_evaluator.evaluate(test_data, response_data, processing_time, error_message)
        
        # Adjust the evaluator name in the result
        result.details["evaluator"] = self.evaluator_name
        result.details["entity_type"] = "scene"
        
        return result

# =============================================================================
# Evaluator Registry and Factory
# =============================================================================

class EvaluatorRegistry:
    """Registry for managing model evaluators"""
    
    def __init__(self):
        self._evaluators = {}
        self._register_default_evaluators()
    
    def _register_default_evaluators(self):
        """Register default evaluators"""
        # Visage evaluators
        self.register("visage_face_recognition", VisageFaceRecognitionEvaluator())
        self.register("visage_gallery", VisageGalleryEvaluator())
        self.register("visage_scene", VisageSceneEvaluator())
        
        # Register entity-specific variants
        self.register("visage_image", VisageFaceRecognitionEvaluator(EntityType.IMAGE))
    
    def register(self, key: str, evaluator: BaseModelEvaluator):
        """Register an evaluator"""
        self._evaluators[key] = evaluator
        logger.info(f"Registered evaluator: {key} ({evaluator.evaluator_name})")
    
    def get_evaluator(self, ai_model: AIModel, action_type: AIActionType, 
                     entity_type: Optional[EntityType] = None) -> Optional[BaseModelEvaluator]:
        """Get the best matching evaluator for given criteria"""
        
        # Try exact match first
        for evaluator in self._evaluators.values():
            if (evaluator.ai_model == ai_model and 
                evaluator.action_type == action_type and
                evaluator.entity_type == entity_type):
                return evaluator
        
        # Try match without entity type
        for evaluator in self._evaluators.values():
            if (evaluator.ai_model == ai_model and 
                evaluator.action_type == action_type and
                evaluator.entity_type is None):
                return evaluator
        
        # Try model + general action match
        if ai_model == AIModel.VISAGE:
            if action_type in [AIActionType.FACIAL_RECOGNITION, AIActionType.IMAGE_IDENTIFICATION]:
                return self._evaluators.get("visage_face_recognition")
            elif action_type == AIActionType.GALLERY_IDENTIFICATION:
                return self._evaluators.get("visage_gallery")
            elif action_type == AIActionType.SCENE_IDENTIFICATION:
                return self._evaluators.get("visage_scene")
        
        logger.warning(f"No evaluator found for {ai_model}, {action_type}, {entity_type}")
        return None
    
    def evaluate_test(self, ai_model: AIModel, action_type: AIActionType, 
                     test_data: Dict[str, Any], response_data: Dict[str, Any],
                     entity_type: Optional[EntityType] = None,
                     processing_time: Optional[float] = None, 
                     error_message: Optional[str] = None) -> Optional[EvaluationResult]:
        """Evaluate a test using the appropriate evaluator"""
        
        evaluator = self.get_evaluator(ai_model, action_type, entity_type)
        if not evaluator:
            return None
        
        return evaluator.evaluate(test_data, response_data, processing_time, error_message)

# Global evaluator registry
evaluator_registry = EvaluatorRegistry()

# =============================================================================
# Convenience Functions
# =============================================================================

def evaluate_ai_test(ai_model: str, action_type: str, test_data: Dict[str, Any], 
                    response_data: Dict[str, Any], entity_type: Optional[str] = None,
                    processing_time: Optional[float] = None, 
                    error_message: Optional[str] = None) -> Optional[EvaluationResult]:
    """
    Convenience function to evaluate AI test results
    
    Args:
        ai_model: AI model name (e.g., "visage")
        action_type: Action type (e.g., "facial_recognition")  
        test_data: Input data sent to AI model
        response_data: Response from AI model
        entity_type: Entity type (optional)
        processing_time: Processing time in seconds
        error_message: Error message if any
        
    Returns:
        EvaluationResult or None if no evaluator found
    """
    try:
        # Convert strings to enums
        ai_model_enum = AIModel(ai_model.lower())
        action_type_enum = AIActionType(action_type.lower())
        entity_type_enum = EntityType(entity_type.lower()) if entity_type else None
        
        return evaluator_registry.evaluate_test(
            ai_model_enum, action_type_enum, test_data, response_data,
            entity_type_enum, processing_time, error_message
        )
    except ValueError as e:
        logger.error(f"Invalid enum value in evaluate_ai_test: {e}")
        return None
    except Exception as e:
        logger.error(f"Error evaluating AI test: {e}")
        return None

def get_default_criteria(ai_model: str, action_type: str, 
                        entity_type: Optional[str] = None) -> Optional[EvaluationCriteria]:
    """Get default evaluation criteria for an AI model and action type"""
    try:
        ai_model_enum = AIModel(ai_model.lower())
        action_type_enum = AIActionType(action_type.lower())
        entity_type_enum = EntityType(entity_type.lower()) if entity_type else None
        
        evaluator = evaluator_registry.get_evaluator(ai_model_enum, action_type_enum, entity_type_enum)
        return evaluator.criteria if evaluator else None
    except ValueError as e:
        logger.error(f"Invalid enum value in get_default_criteria: {e}")
        return None