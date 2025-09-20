// =============================================================================
// Gallery Action Handler - Batch processing for gallery operations
// =============================================================================

import { ActionResult, PageContext, AISettings } from './ImageActionHandler';

// GraphQL query for gallery data
const findGallery = async (id: string) => {
  const query = `
    query FindGallery($id: ID!) {
      findGallery(id: $id) {
        id
        title
        images {
          id
          title
          paths {
            image
            preview
            thumbnail
          }
        }
      }
    }
  `;

  try {
    const response = await fetch('/graphql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        variables: { id }
      })
    });

    if (!response.ok) {
      throw new Error(`GraphQL request failed: ${response.status} ${response.statusText}`);
    }

    const result = await response.json();
    if (result.errors) {
      throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
    }

    return result.data?.findGallery || null;
  } catch (error) {
    console.error('Failed to fetch gallery data:', error);
    throw error;
  }
};

export class GalleryActionHandler {

  async execute(action: string, serviceName: string, context: PageContext, settings: AISettings): Promise<ActionResult> {
    switch (action) {
      case 'analyze-gallery-batch':
        return await this.handleGalleryBatchAnalysis(serviceName, context, settings);
      
      default:
        return {
          success: false,
          message: `Unknown gallery action: ${action}`
        };
    }
  }

  private async handleGalleryBatchAnalysis(serviceName: string, context: PageContext, settings: AISettings): Promise<ActionResult> {
    if (!context.isDetailView || !context.entityId) {
      return {
        success: false,
        message: 'Gallery batch analysis is only available on specific gallery pages'
      };
    }

    try {
      // Check if ImageHandler is available for batch processing
      const ImageHandler = (window as any).ImageHandler;
      if (!ImageHandler) {
        throw new Error('ImageHandler not available for batch processing');
      }

      const imageHandler = new ImageHandler();
      
      // Get all images in the gallery
      const galleryData = await findGallery(context.entityId);
      
      if (!galleryData || !galleryData.images || galleryData.images.length === 0) {
        return {
          success: false,
          message: 'No images found in this gallery'
        };
      }

      const imageIds = galleryData.images.map((image: any) => image.id);
      
      // Process gallery images as batch using ImageHandler
      const options = {
        maxConcurrent: 2,
        skipErrors: true
      };

      const batchResults = await imageHandler.batchGetImagesWithBase64(imageIds, options);
      
      if (batchResults.length === 0) {
        return {
          success: false,
          message: 'Failed to process any images from this gallery'
        };
      }

      // Create batch job data
      const jobData = await imageHandler.createBatchJobData(
        batchResults,
        'gallery_batch_analysis',
        {
          gallery_id: context.entityId,
          gallery_title: galleryData.title,
          source: 'ai_button_gallery_batch'
        }
      );

      // Submit batch job
      const images = jobData.tasks.map((task: any) => task.input_data.image_data);
      const jobPayload = {
        images: images,
        visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
        config: {
          threshold: settings.visageThreshold || 0.7,
          job_name: `Gallery Batch: ${galleryData.title || 'Untitled'}`,
          user_id: 'ai_overhaul_button',
          session_id: 'gallery_batch_session',
          additional_params: {
            max_faces: 10,
            return_embeddings: false,
            source: 'ai_overhaul_gallery_batch',
            entity_type: 'gallery',
            gallery_id: context.entityId
          }
        }
      };

      const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/job`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(jobPayload)
      });

      if (!response.ok) {
        throw new Error(`Failed to create batch job: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();

      return {
        success: true,
        message: `Gallery batch analysis started! Processing ${images.length} images from "${galleryData.title}".`,
        taskId: result.job_id || result.id,
        data: result
      };

    } catch (error: any) {
      console.error('Gallery batch analysis failed:', error);
      return {
        success: false,
        message: `Failed to start gallery batch analysis: ${error.message}`
      };
    }
  }
}