from datetime import datetime
import logging

from fastapi import APIRouter, HTTPException

from database.interactions_service import interactions_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai-tests", tags=["ai-tests"])

@router.get("/{test_id}")
async def get_ai_test_details(test_id: str):
    """Get detailed information about a specific AI test"""
    try:
        test_info = interactions_service.get_ai_test(test_id)
        if not test_info:
            raise HTTPException(status_code=404, detail=f"AI test {test_id} not found")
        
        return test_info.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI test details for {test_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve AI test details")
    
@router.get("/{test_id}/results")
async def get_ai_test_results(test_id: str):
    """Get detailed results for a specific AI test including response data"""
    try:
        test_info = interactions_service.get_ai_test(test_id)
        if not test_info:
            raise HTTPException(status_code=404, detail=f"AI test {test_id} not found")
        
        # Return test info with full response data for overlay display
        test_data = test_info.dict()
        logger.info(f"Retrieved test {test_id}: response_data={bool(test_data.get('response_data'))} - Keys: {list(test_data.get('response_data', {}).keys()) if test_data.get('response_data') else 'None'}")
        
        # Transform response data to match overlay format expectations
        if test_data.get('response_data'):
            response = test_data['response_data']
            
            # For single image results (image processing)
            if test_data.get('entity_type') == 'image' and 'performers' in response:
                # Format as single image result
                result = {
                    'success': test_data.get('status') == 'completed',
                    'performers': response.get('performers', []),
                    'entity_id': test_data.get('entity_id'),
                    'entity_type': test_data.get('entity_type'),
                    'test_id': test_id,
                    'processing_time': test_data.get('processing_time'),
                    'confidence_scores': test_data.get('confidence_scores', []),
                    'max_confidence': test_data.get('max_confidence')
                }
                return result
            
            # For gallery results (batch processing)
            elif test_data.get('entity_type') == 'gallery' and 'performers' in response:
                # Format as gallery batch result
                result = {
                    'success': test_data.get('status') == 'completed',
                    'galleryId': test_data.get('entity_id'),
                    'entity_type': test_data.get('entity_type'),
                    'test_id': test_id,
                    'performers': response.get('performers', []),
                    'processingResults': response.get('processingResults', []),
                    'totalImages': len(response.get('processingResults', [])),
                    'processedImages': len([r for r in response.get('processingResults', []) if r.get('success')]),
                    'skippedImages': len([r for r in response.get('processingResults', []) if not r.get('success')]),
                    'totalProcessingTime': test_data.get('processing_time'),
                    'error': test_data.get('error_message') if test_data.get('status') == 'failed' else None
                }
                return result
            
            # For scene results
            elif test_data.get('entity_type') == 'scene' and 'performers' in response:
                # Format as scene batch result
                result = {
                    'success': test_data.get('status') == 'completed',
                    'sceneId': test_data.get('entity_id'),
                    'entity_type': test_data.get('entity_type'),
                    'test_id': test_id,
                    'performers': response.get('performers', []),
                    'processingResults': response.get('processingResults', []),
                    'totalFrames': len(response.get('processingResults', [])),
                    'processedFrames': len([r for r in response.get('processingResults', []) if r.get('success')]),
                    'skippedFrames': len([r for r in response.get('processingResults', []) if not r.get('success')]),
                    'totalProcessingTime': test_data.get('processing_time'),
                    'error': test_data.get('error_message') if test_data.get('status') == 'failed' else None
                }
                return result
        
        # Fallback - return raw test data
        return {
            'success': test_data.get('status') == 'completed',
            'test_id': test_id,
            'entity_id': test_data.get('entity_id'),
            'entity_type': test_data.get('entity_type'),
            'rawResponse': test_data.get('response_data'),
            'error': test_data.get('error_message') if test_data.get('status') == 'failed' else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI test results for {test_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve AI test results")



@router.post("/{test_id}/cancel")
async def cancel_ai_test(test_id: str):
    """Cancel a specific AI test"""
    try:
        result = interactions_service.cancel_ai_test(test_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"AI test {test_id} not found or cannot be cancelled")
        
        return {
            "success": True,
            "message": f"Successfully cancelled AI test {test_id}",
            "test": result.dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel AI test {test_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel AI test")