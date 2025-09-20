// =============================================================================
// Image Action Handlers
// =============================================================================

import { ActionHandler, ActionResult, PageContext, AISettings } from './ActionTypes';

export class ImageActionHandler implements ActionHandler {
  async execute(
    action: string,
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    switch (action) {
      case 'analyze-faces':
        return this.handleFaceAnalysis(serviceName, context, settings);
      
      case 'analyze-content':
        return this.handleContentAnalysis(serviceName, context, settings);
      
      default:
        return {
          success: false,
          message: `Unknown action: ${action}`
        };
    }
  }

  private async handleFaceAnalysis(
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    if (!context.isDetailView || !context.entityId) {
      return {
        success: false,
        message: 'Face analysis is only available on specific image or scene pages'
      };
    }

    try {
      let taskData = {};

      if (context.page === 'images') {
        // Image face analysis
        taskData = {
          image_id: context.entityId,
          threshold: settings.visageThreshold || 0.7,
          visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
          additional_params: {
            max_faces: 10,
            return_embeddings: false,
            source: 'ai_overhaul_navbar_button',
            // Add entity tracking information
            entity_type: 'image',
            entity_id: context.entityId
          }
        };
      } else if (context.page === 'scenes') {
        // Scene face analysis
        taskData = {
          scene_id: context.entityId,
          threshold: settings.visageThreshold || 0.7,
          visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
          additional_params: {
            max_faces: 10,
            return_embeddings: false,
            source: 'ai_overhaul_navbar_button',
            // Add entity tracking information
            entity_type: 'scene',
            entity_id: context.entityId
          }
        };
      } else {
        return {
          success: false,
          message: `Face analysis not supported for ${context.page} context`
        };
      }

      // Create Visage task
      const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(taskData)
      });

      if (response.ok) {
        const result = await response.json();
        console.log('AI task created:', result);
        
        return {
          success: true,
          message: result.task_id 
            ? `${serviceName} analysis started! Task ID: ${result.task_id}`
            : `${serviceName} analysis completed successfully!`,
          taskId: result.task_id,
          data: result
        };
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

    } catch (error: any) {
      console.error('Face analysis failed:', error);
      return {
        success: false,
        message: `${serviceName} analysis failed: ${error.message}`
      };
    }
  }

  private async handleContentAnalysis(
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult> {
    // Placeholder for content analysis implementation
    return {
      success: false,
      message: `${serviceName} content analysis is not yet implemented for this content type`
    };
  }
}

export default ImageActionHandler;