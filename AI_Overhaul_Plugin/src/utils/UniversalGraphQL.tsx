// =============================================================================
// Universal GraphQL Utility Component
// =============================================================================
// Provides reusable GraphQL query functions for common Stash operations

interface UniversalGraphQLProps {
  React: any;
}

const UniversalGraphQL = ({ React }: UniversalGraphQLProps) => {
  // Use direct fetch to GraphQL endpoint like other working code
  const graphqlEndpoint = '/graphql';

  // =============================================================================
  // IMAGE QUERIES
  // =============================================================================
  
  const getImageUrl = async (imageId: string): Promise<string | null> => {
    try {
      console.log('UniversalGraphQL: Fetching image URL for ID:', imageId);
      
      const imageQuery = `
        query FindImage($id: ID!) {
          findImage(id: $id) {
            paths {
              image
            }
          }
        }
      `;
      
      const response = await fetch(graphqlEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: imageQuery, variables: { id: imageId } })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      }
      console.log('UniversalGraphQL: Image query response:', result);
      
      if (result.data?.findImage?.paths?.image) {
        const imageUrl = result.data.findImage.paths.image;
        console.log('UniversalGraphQL: Successfully resolved image URL:', imageUrl);
        return imageUrl;
      } else {
        console.warn('UniversalGraphQL: No image path found for ID:', imageId);
        return null;
      }
    } catch (error) {
      console.error('UniversalGraphQL: Error fetching image URL for ID:', imageId, error);
      return null;
    }
  };

  const getImageDetails = async (imageId: string) => {
    try {
      console.log('UniversalGraphQL: Fetching image details for ID:', imageId);
      
      const imageQuery = `
        query FindImage($id: ID!) {
          findImage(id: $id) {
            id
            title
            paths {
              image
              thumbnail
            }
            file {
              size
              width
              height
            }
          }
        }
      `;
      
      const response = await fetch(graphqlEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: imageQuery, variables: { id: imageId } })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      };
      console.log('UniversalGraphQL: Image details response:', result);
      
      return result.data?.findImage || null;
    } catch (error) {
      console.error('UniversalGraphQL: Error fetching image details for ID:', imageId, error);
      return null;
    }
  };

  // =============================================================================
  // SCENE QUERIES  
  // =============================================================================
  
  const getSceneUrl = async (sceneId: string): Promise<string | null> => {
    try {
      console.log('UniversalGraphQL: Fetching scene URL for ID:', sceneId);
      
      const sceneQuery = `
        query FindScene($id: ID!) {
          findScene(id: $id) {
            paths {
              screenshot
            }
          }
        }
      `;
      
      const response = await fetch(graphqlEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: sceneQuery, variables: { id: sceneId } })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      }
      console.log('UniversalGraphQL: Scene query response:', result);
      
      if (result.data?.findScene?.paths?.screenshot) {
        const sceneUrl = result.data.findScene.paths.screenshot;
        console.log('UniversalGraphQL: Successfully resolved scene URL:', sceneUrl);
        return sceneUrl;
      } else {
        console.warn('UniversalGraphQL: No scene screenshot found for ID:', sceneId);
        return null;
      }
    } catch (error) {
      console.error('UniversalGraphQL: Error fetching scene URL for ID:', sceneId, error);
      return null;
    }
  };

  // =============================================================================
  // GALLERY QUERIES
  // =============================================================================
  
  const getGalleryUrl = async (galleryId: string): Promise<string | null> => {
    try {
      console.log('UniversalGraphQL: Fetching gallery URL for ID:', galleryId);
      
      const galleryQuery = `
        query FindGallery($id: ID!) {
          findGallery(id: $id) {
            cover {
              paths {
                image
              }
            }
          }
        }
      `;
      
      const response = await fetch(graphqlEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: galleryQuery, variables: { id: galleryId } })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      }
      console.log('UniversalGraphQL: Gallery query response:', result);
      
      if (result.data?.findGallery?.cover?.paths?.image) {
        const galleryUrl = result.data.findGallery.cover.paths.image;
        console.log('UniversalGraphQL: Successfully resolved gallery URL:', galleryUrl);
        return galleryUrl;
      } else {
        console.warn('UniversalGraphQL: No gallery cover found for ID:', galleryId);
        return null;
      }
    } catch (error) {
      console.error('UniversalGraphQL: Error fetching gallery URL for ID:', galleryId, error);
      return null;
    }
  };

  // =============================================================================
  // UNIVERSAL ENTITY RESOLVER
  // =============================================================================
  
  const resolveEntityUrl = async (entityType: string, entityId: string): Promise<string | null> => {
    console.log('UniversalGraphQL: Resolving URL for entity:', { entityType, entityId });
    
    switch (entityType?.toLowerCase()) {
      case 'image':
        return await getImageUrl(entityId);
      case 'scene':
        return await getSceneUrl(entityId);  
      case 'gallery':
        return await getGalleryUrl(entityId);
      default:
        console.warn('UniversalGraphQL: Unknown entity type:', entityType);
        // Try image as fallback since most AI operations work on images
        return await getImageUrl(entityId);
    }
  };

  // =============================================================================
  // TASK DATA URL RESOLVER
  // =============================================================================
  
  const resolveImageFromTaskData = async (taskData: any): Promise<{ url: string | null; id: string | null }> => {
    console.log('UniversalGraphQL: Resolving image from task data:', taskData);
    
    let resolvedUrl = null;
    let resolvedId = null;
    
    try {
      // Try entity tracking fields first
      if (taskData.entity_type && taskData.entity_id) {
        resolvedId = taskData.entity_id;
        resolvedUrl = await resolveEntityUrl(taskData.entity_type, taskData.entity_id);
        if (resolvedUrl) {
          console.log('UniversalGraphQL: Resolved via entity tracking:', { resolvedId, resolvedUrl });
          return { url: resolvedUrl, id: resolvedId };
        }
      }
      
      // Try direct image_id fields
      if (taskData.image_id) {
        resolvedId = taskData.image_id;
        resolvedUrl = await getImageUrl(taskData.image_id);
        if (resolvedUrl) {
          console.log('UniversalGraphQL: Resolved via image_id:', { resolvedId, resolvedUrl });
          return { url: resolvedUrl, id: resolvedId };
        }
      }
      
      // Try alternative ID fields
      if (taskData.entity_id) {
        resolvedId = taskData.entity_id;
        resolvedUrl = await getImageUrl(taskData.entity_id);
        if (resolvedUrl) {
          console.log('UniversalGraphQL: Resolved via entity_id fallback:', { resolvedId, resolvedUrl });
          return { url: resolvedUrl, id: resolvedId };
        }
      }
      
      // Try base64 data fallbacks
      if (taskData.base64_image) {
        resolvedUrl = `data:image/jpeg;base64,${taskData.base64_image}`;
        resolvedId = taskData.image_id || 'base64-data';
        console.log('UniversalGraphQL: Using base64 image data');
        return { url: resolvedUrl, id: resolvedId };
      }
      
      if (taskData.image && typeof taskData.image === 'string' && taskData.image.startsWith('/9j/')) {
        resolvedUrl = `data:image/jpeg;base64,${taskData.image}`;
        resolvedId = taskData.image_id || 'base64-image';
        console.log('UniversalGraphQL: Using base64 from image field');
        return { url: resolvedUrl, id: resolvedId };
      }
      
      // Try direct image_url
      if (taskData.image_url) {
        resolvedUrl = taskData.image_url;
        resolvedId = taskData.image_url.split('/').pop() || 'direct-url';
        console.log('UniversalGraphQL: Using direct image_url:', resolvedUrl);
        return { url: resolvedUrl, id: resolvedId };
      }
      
      console.warn('UniversalGraphQL: Could not resolve image from task data. Available fields:', Object.keys(taskData));
      return { url: null, id: null };
      
    } catch (error) {
      console.error('UniversalGraphQL: Error resolving image from task data:', error);
      return { url: null, id: null };
    }
  };

  // =============================================================================
  // RETURN API
  // =============================================================================
  
  return {
    getImageUrl,
    getImageDetails,
    getSceneUrl,
    getGalleryUrl,
    resolveEntityUrl,
    resolveImageFromTaskData
  };
};

// Expose globally for plugin usage
(window as any).UniversalGraphQL = UniversalGraphQL;

export default UniversalGraphQL;