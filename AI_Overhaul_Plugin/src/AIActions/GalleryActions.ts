// =============================================================================
// Gallery Action Handlers
// =============================================================================

import { ActionHandler, ActionResult, PageContext, AISettings } from './ActionTypes';

export class GalleryActionHandler implements ActionHandler {
  async execute(
    action: string,
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    switch (action) {
      case 'analyze-gallery':
        return this.handleGalleryAnalysis(serviceName, context, settings);
      
      case 'batch-process-images':
        return this.handleBatchImageProcessing(serviceName, context, settings);
      
      default:
        return {
          success: false,
          message: `Unknown gallery action: ${action}`
        };
    }
  }

  private async handleGalleryAnalysis(
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    if (!context.isDetailView || !context.entityId || context.page !== 'galleries') {
      return {
        success: false,
        message: 'Gallery analysis is only available on gallery detail pages'
      };
    }

    try {
      console.log('Starting gallery analysis for:', context.entityId);

      // Initialize ImageHandler for batch processing
      const ImageHandler = (window as any).ImageHandler;
      if (!ImageHandler) {
        throw new Error('ImageHandler not available');
      }

      const imageHandler = new ImageHandler();

      // Set up progress tracking options
      const options = {
        maxConcurrent: 2, // Conservative to avoid overwhelming
        skipErrors: true,
        onProgress: (processed: number, total: number, current?: any) => {
          console.log(`Gallery processing progress: ${processed}/${total}${current ? ` - ${current.title || current.id}` : ''}`);
          // Could emit progress events here for UI updates
        },
        onError: (error: Error, imageData: any) => {
          console.error(`Error processing image ${imageData.id}:`, error);
        }
      };

      // Create gallery job data using batch processing
      const { galleryData, jobData } = await imageHandler.createGalleryJobData(
        context.entityId,
        options,
        'gallery_visage_analysis'
      );

      console.log('Gallery job data created:', jobData);

      // Submit job to AI server using existing pattern
      const taskData = {
        gallery_id: context.entityId,
        job_type: 'gallery_batch_analysis',
        visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
        batch_data: jobData,
        additional_params: {
          threshold: settings.visageThreshold || 0.7,
          max_faces: 10,
          source: 'ai_overhaul_gallery_action',
          entity_type: 'gallery',
          entity_id: context.entityId,
          total_images: jobData.tasks.length
        }
      };

      const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/gallery`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(taskData)
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Gallery AI task created:', result);
        
        return {
          success: true,
          message: result.task_id 
            ? `${serviceName} gallery analysis started! Processing ${jobData.tasks.length} images. Task ID: ${result.task_id}`
            : `${serviceName} gallery analysis completed successfully!`,
          taskId: result.task_id,
          data: {
            ...result,
            galleryData,
            totalImages: jobData.tasks.length,
            type: 'gallery_batch'
          }
        };
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

    } catch (error: any) {
      console.error('Gallery analysis failed:', error);
      return {
        success: false,
        message: `${serviceName} gallery analysis failed: ${error.message}`
      };
    }
  }

  private async handleBatchImageProcessing(
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    if (!context.isDetailView || !context.entityId || context.page !== 'galleries') {
      return {
        success: false,
        message: 'Batch image processing is only available on gallery detail pages'
      };
    }

    try {
      console.log('Starting batch image processing for gallery:', context.entityId);

      // Get ImageHandler
      const ImageHandler = (window as any).ImageHandler;
      if (!ImageHandler) {
        throw new Error('ImageHandler not available');
      }

      const imageHandler = new ImageHandler();

      // First get gallery data to see how many images we're dealing with
      const galleryData = await imageHandler.findGallery(context.entityId);
      if (!galleryData) {
        throw new Error('Gallery not found');
      }

      const imageCount = galleryData.images.length;
      if (imageCount === 0) {
        return {
          success: false,
          message: 'Gallery contains no images to process'
        };
      }

      // Create batch processing job
      const options = {
        maxConcurrent: 3,
        skipErrors: true
      };

      const { jobData } = await imageHandler.createGalleryJobData(
        context.entityId,
        options,
        'batch_image_processing'
      );

      // Submit as individual tasks that can be tracked
      const taskIds: string[] = [];
      
      for (const task of jobData.tasks) {
        const individualTaskData = {
          image_id: task.input_data.entity_id,
          threshold: settings.visageThreshold || 0.7,
          visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
          additional_params: {
            ...task.metadata,
            max_faces: 10,
            source: 'ai_overhaul_batch_processing',
            entity_type: 'image',
            entity_id: task.input_data.entity_id,
            batch_context: {
              gallery_id: context.entityId,
              gallery_title: galleryData.title,
              batch_size: jobData.tasks.length
            }
          }
        };

        const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/task`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(individualTaskData)
        });

        if (response.ok) {
          const result = await response.json();
          if (result.task_id) {
            taskIds.push(result.task_id);
          }
        }
      }

      return {
        success: true,
        message: `${serviceName} batch processing started! Processing ${imageCount} images from gallery "${galleryData.title || 'Untitled'}". ${taskIds.length} tasks created.`,
        taskId: taskIds.length > 0 ? taskIds[0] : undefined, // Return first task ID for primary tracking
        data: {
          taskIds,
          galleryData,
          totalImages: imageCount,
          type: 'batch_processing'
        }
      };

    } catch (error: any) {
      console.error('Batch image processing failed:', error);
      return {
        success: false,
        message: `${serviceName} batch processing failed: ${error.message}`
      };
    }
  }

  // Get available actions for gallery context
  getAvailableActions(context: PageContext): string[] {
    const actions: string[] = [];

    if (context.page === 'galleries' && context.isDetailView) {
      actions.push('analyze-gallery', 'batch-process-images');
    }

    return actions;
  }
}

export default GalleryActionHandler;