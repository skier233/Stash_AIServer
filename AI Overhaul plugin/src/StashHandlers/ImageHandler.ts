// =============================================================================
// Stash GraphQL Image Handler
// =============================================================================

export interface ImageData {
  id: string;
  title?: string;
  urls?: string[];
  galleries?: Array<{
    id: string;
    title: string;
  }>;
  paths: {
    image?: string;
    preview?: string;
    thumbnail?: string;
  };
}

export interface BatchImageData {
  imageData: ImageData;
  base64: string;
}

export interface BatchProcessingOptions {
  maxConcurrent?: number;
  skipErrors?: boolean;
  onProgress?: (processed: number, total: number, current?: ImageData) => void;
  onError?: (error: Error, imageData: ImageData) => void;
}

export interface GalleryData {
  id: string;
  title?: string;
  images: {
    id: string;
    title?: string;
    paths: {
      image?: string;
      preview?: string;
      thumbnail?: string;
    };
  }[];
}

export interface GraphQLResponse<T> {
  data?: T;
  errors?: Array<{
    message: string;
    locations?: Array<{ line: number; column: number }>;
    path?: string[];
  }>;
}

export class ImageHandler {
  private graphqlEndpoint: string;

  constructor(graphqlEndpoint: string = '/graphql') {
    this.graphqlEndpoint = graphqlEndpoint;
  }

  // Fetch image data using GraphQL
  async findImage(id: string): Promise<ImageData | null> {
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
            __typename
          }
        }
      }
    `;

    try {
      const response = await fetch(this.graphqlEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          variables: { id }
        })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result: GraphQLResponse<{ findImage: ImageData }> = await response.json();

      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map(e => e.message).join(', ')}`);
      }

      return result.data?.findImage || null;
    } catch (error) {
      console.error('Failed to fetch image data:', error);
      throw error;
    }
  }

  // Convert image URL to base64
  async imageToBase64(imageUrl: string): Promise<string> {
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
          reject(new Error(`Failed to convert image to base64: ${error}`));
        }
      };
      
      img.onerror = () => {
        reject(new Error(`Failed to load image from URL: ${imageUrl}`));
      };
      
      img.src = imageUrl;
    });
  }

  // Get image data with base64 encoding
  async getImageWithBase64(id: string): Promise<{ imageData: ImageData; base64: string } | null> {
    try {
      const imageData = await this.findImage(id);
      
      if (!imageData) {
        throw new Error('Image not found');
      }

      // Try different image paths in order of preference
      const imageUrl = imageData.paths.image || imageData.paths.preview || imageData.paths.thumbnail;
      
      if (!imageUrl) {
        throw new Error('No valid image path found');
      }

      console.log('Converting image to base64:', imageUrl);
      const base64 = await this.imageToBase64(imageUrl);
      
      return {
        imageData,
        base64
      };
    } catch (error) {
      console.error('Failed to get image with base64:', error);
      throw error;
    }
  }

  // =============================================================================
  // BATCH PROCESSING METHODS
  // =============================================================================

  // Fetch gallery data with images  
  async findGallery(id: string): Promise<GalleryData | null> {
    // First get gallery basic info
    const galleryQuery = `
      query FindGallery($id: ID!) {
        findGallery(id: $id) {
          id
          title
          urls
          cover {
            urls
          }
        }
      }
    `;

    // Then get all images in the gallery
    const imagesQuery = `
      query FindImages($gallery_filter: MultiCriterionInput) {
        findImages(
          image_filter: { galleries: $gallery_filter }
          filter: { per_page: -1 }
        ) {
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
      // First fetch gallery info
      const galleryResponse = await fetch(this.graphqlEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: galleryQuery,
          variables: { id }
        })
      });

      if (!galleryResponse.ok) {
        throw new Error(`Gallery GraphQL request failed: ${galleryResponse.status}`);
      }

      const galleryResult: GraphQLResponse<{ findGallery: any }> = await galleryResponse.json();

      if (galleryResult.errors) {
        throw new Error(`Gallery GraphQL errors: ${galleryResult.errors.map(e => e.message).join(', ')}`);
      }

      const galleryInfo = galleryResult.data?.findGallery;
      if (!galleryInfo) {
        return null;
      }

      // Then fetch images in the gallery
      const imagesResponse = await fetch(this.graphqlEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: imagesQuery,
          variables: { 
            gallery_filter: { 
              value: [id], 
              modifier: "INCLUDES" 
            } 
          }
        })
      });

      if (!imagesResponse.ok) {
        throw new Error(`Images GraphQL request failed: ${imagesResponse.status}`);
      }

      const imagesResult: GraphQLResponse<{ findImages: { images: any[] } }> = await imagesResponse.json();

      if (imagesResult.errors) {
        throw new Error(`Images GraphQL errors: ${imagesResult.errors.map(e => e.message).join(', ')}`);
      }

      const images = imagesResult.data?.findImages?.images || [];

      // Combine gallery info with images
      return {
        id: galleryInfo.id,
        title: galleryInfo.title,
        images: images.map((img: any) => ({
          id: img.id,
          title: img.title,
          paths: img.paths
        }))
      };

    } catch (error) {
      console.error('Failed to fetch gallery data:', error);
      throw error;
    }
  }

  // Process multiple images with base64 conversion
  async batchGetImagesWithBase64(
    imageIds: string[], 
    options: BatchProcessingOptions = {}
  ): Promise<BatchImageData[]> {
    const {
      maxConcurrent = 3,
      skipErrors = true,
      onProgress,
      onError
    } = options;

    const results: BatchImageData[] = [];
    let processed = 0;

    console.log(`Starting batch processing of ${imageIds.length} images with max ${maxConcurrent} concurrent`);

    // Process images in batches to avoid overwhelming the system
    for (let i = 0; i < imageIds.length; i += maxConcurrent) {
      const batch = imageIds.slice(i, i + maxConcurrent);
      
      const batchPromises = batch.map(async (id) => {
        try {
          const imageData = await this.findImage(id);
          if (!imageData) {
            throw new Error(`Image ${id} not found`);
          }

          const imageUrl = imageData.paths.image || imageData.paths.preview || imageData.paths.thumbnail;
          if (!imageUrl) {
            throw new Error(`No valid image path found for image ${id}`);
          }

          const base64 = await this.imageToBase64(imageUrl);
          
          processed++;
          if (onProgress) {
            onProgress(processed, imageIds.length, imageData);
          }

          return { imageData, base64 };
        } catch (error) {
          console.error(`Failed to process image ${id}:`, error);
          
          if (onError) {
            // Create minimal image data for error callback
            const errorImageData: ImageData = {
              id,
              title: `Image ${id}`,
              paths: {}
            };
            onError(error as Error, errorImageData);
          }

          if (!skipErrors) {
            throw error;
          }
          
          processed++;
          if (onProgress) {
            onProgress(processed, imageIds.length);
          }
          
          return null;
        }
      });

      const batchResults = await Promise.all(batchPromises);
      
      // Add successful results to the final array
      for (const result of batchResults) {
        if (result) {
          results.push(result);
        }
      }
    }

    console.log(`Batch processing completed: ${results.length}/${imageIds.length} images processed successfully`);
    return results;
  }

  // Process all images in a gallery
  async batchProcessGallery(
    galleryId: string,
    options: BatchProcessingOptions = {}
  ): Promise<{ galleryData: GalleryData; batchResults: BatchImageData[] }> {
    console.log(`Starting gallery batch processing for gallery: ${galleryId}`);
    
    const galleryData = await this.findGallery(galleryId);
    if (!galleryData) {
      throw new Error(`Gallery ${galleryId} not found`);
    }

    console.log(`Gallery "${galleryData.title || galleryId}" contains ${galleryData.images.length} images`);

    const imageIds = galleryData.images.map(img => img.id);
    const batchResults = await this.batchGetImagesWithBase64(imageIds, options);

    return {
      galleryData,
      batchResults
    };
  }

  // Create job data structure for AI processing
  async createBatchJobData(
    images: BatchImageData[],
    jobType: string = 'batch_analysis',
    metadata?: any
  ): Promise<{
    job_type: string;
    tasks: Array<{
      task_type: string;
      input_data: {
        entity_type: string;
        entity_id: string;
        entity: any; // Full entity data
        image_data: string;
        image_title?: string;
      };
      metadata?: any;
    }>;
    metadata?: any;
  }> {
    const tasks = images.map((batchImage, index) => ({
      task_type: 'image_analysis',
      input_data: {
        entity_type: 'image',
        entity_id: batchImage.imageData.id,
        entity: {
          id: batchImage.imageData.id,
          title: batchImage.imageData.title,
          paths: batchImage.imageData.paths,
          galleries: batchImage.imageData.galleries || []
        }, // Store full entity data for easy access
        image_data: batchImage.base64,
        image_title: batchImage.imageData.title || `Image ${index + 1}`
      },
      metadata: {
        image_index: index,
        total_images: images.length,
        ...metadata
      }
    }));

    return {
      job_type: jobType,
      tasks,
      metadata: {
        total_tasks: tasks.length,
        batch_type: 'images',
        created_at: new Date().toISOString(),
        ...metadata
      }
    };
  }

  // Create gallery job data
  async createGalleryJobData(
    galleryId: string,
    options: BatchProcessingOptions = {},
    jobType: string = 'gallery_analysis'
  ): Promise<{
    galleryData: GalleryData;
    jobData: any;
  }> {
    console.log(`Creating gallery job data for: ${galleryId}`);
    
    const { galleryData, batchResults } = await this.batchProcessGallery(galleryId, options);
    
    const jobData = await this.createBatchJobData(
      batchResults,
      jobType,
      {
        gallery_id: galleryId,
        gallery_title: galleryData.title
      }
    );

    return {
      galleryData,
      jobData
    };
  }
}

export default ImageHandler;

// Make ImageHandler available globally for plugin system
(window as any).ImageHandler = ImageHandler;