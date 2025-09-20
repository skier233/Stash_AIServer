// =============================================================================
// Image Action Handler - Face analysis for images and scenes
// =============================================================================

export interface ActionResult {
  success: boolean;
  message: string;
  taskId?: string;
  data?: any;
}

export interface PageContext {
  page: string;
  entityId: string | null;
  isDetailView: boolean;
}

export interface AISettings {
  stashAIServer: string;
  port: string | number;
  visageThreshold?: number;
}

// Image to base64 conversion utility
const imageToBase64 = async (imageUrl: string): Promise<string> => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      if (!ctx) {
        reject(new Error('Failed to get canvas context'));
        return;
      }
      
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      
      try {
        const dataURL = canvas.toDataURL('image/jpeg', 0.9);
        const base64 = dataURL.replace(/^data:image\/[a-z]+;base64,/, '');
        resolve(base64);
      } catch (error) {
        reject(new Error(`Failed to convert image to base64: ${(error as Error).message}`));
      }
    };
    
    img.onerror = () => {
      reject(new Error(`Failed to load image: ${imageUrl}`));
    };
    
    img.src = imageUrl;
  });
};

// GraphQL query for image data
const findImage = async (id: string) => {
  const query = `
    query FindImage($id: ID!) {
      findImage(id: $id) {
        id
        title
        urls
        galleries {
          id
          title
        }
        paths {
          image
          preview
          thumbnail
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

    return result.data?.findImage || null;
  } catch (error) {
    console.error('Failed to fetch image data:', error);
    throw error;
  }
};

export class ImageActionHandler {
  
  async execute(action: string, serviceName: string, context: PageContext, settings: AISettings): Promise<ActionResult> {
    if (!context.isDetailView || !context.entityId) {
      return {
        success: false,
        message: 'This action is only available on specific image or scene pages'
      };
    }

    switch (action) {
      case 'analyze-faces':
      case 'analyze-scene':
        return await this.handleFaceAnalysis(serviceName, context, settings);
      
      case 'analyze-content':
        return {
          success: false,
          message: 'Content analysis is not yet implemented'
        };
      
      default:
        return {
          success: false,
          message: `Unknown action: ${action}`
        };
    }
  }

  private async handleFaceAnalysis(serviceName: string, context: PageContext, settings: AISettings): Promise<ActionResult> {
    try {
      if (context.page === 'images') {
        // Handle image face analysis
        const imageData = await findImage(context.entityId!);
        
        if (!imageData) {
          throw new Error('Image not found');
        }

        const imageUrl = imageData.paths.image || imageData.paths.preview || imageData.paths.thumbnail;
        if (!imageUrl) {
          throw new Error('No valid image path found');
        }

        const base64Data = await imageToBase64(imageUrl);

        const taskData = {
          service_type: "visage",
          image_data: {
            stash_image_id: context.entityId!,
            image_base64: base64Data,
            stash_image_title: imageData.title || `Image ${context.entityId}`,
            image_metadata: {
              urls: imageData.urls || [],
              galleries: imageData.galleries || []
            }
          },
          config: {
            threshold: settings.visageThreshold || 0.7,
            service_config: {
              api_endpoint: `http://${settings.stashAIServer}:9997/api/predict_1`,
              max_faces: 10,
              return_embeddings: false,
              detection_mode: "multi"
            },
            source: 'ai_overhaul_button'
          }
        };

        const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/task`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData)
        });

        if (!response.ok) {
          throw new Error(`Failed to create task: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();

        return {
          success: true,
          message: `${serviceName} task created successfully! Processing will begin shortly.`,
          taskId: result.task_id || result.id,
          data: result
        };

      } else if (context.page === 'scenes') {
        // Handle scene face analysis
        const taskData = {
          service_type: "visage",
          scene_id: context.entityId,
          config: {
            threshold: settings.visageThreshold || 0.7,
            service_config: {
              api_endpoint: `http://${settings.stashAIServer}:9997/api/predict_1`,
              max_faces: 10,
              return_embeddings: false,
              detection_mode: "multi"
            },
            source: 'ai_overhaul_button'
          }
        };

        const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/task`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData)
        });

        if (!response.ok) {
          throw new Error(`Failed to create task: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();

        return {
          success: true,
          message: `${serviceName} task created successfully! Processing will begin shortly.`,
          taskId: result.task_id || result.id,
          data: result
        };
      }

      return {
        success: false,
        message: 'Face analysis is not supported for this page type'
      };

    } catch (error: any) {
      console.error(`${serviceName} failed:`, error);
      return {
        success: false,
        message: `Failed to start ${serviceName}: ${error.message}`
      };
    }
  }
}