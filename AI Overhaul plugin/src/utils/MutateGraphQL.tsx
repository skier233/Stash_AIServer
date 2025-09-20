// =============================================================================
// Mutate GraphQL Utility Component
// =============================================================================
// Provides GraphQL mutation functions for performer management and entity updates

interface MutateGraphQLProps {
  React: any;
}

const MutateGraphQL = ({ React }: MutateGraphQLProps) => {
  // Use direct fetch to GraphQL endpoint like other working code
  const graphqlEndpoint = '/graphql';

  // =============================================================================
  // PERFORMER QUERIES & MUTATIONS
  // =============================================================================
  
  const searchPerformers = async (name: string) => {
    try {
      console.log('MutateGraphQL: Searching for performers with name:', name);
      
      const searchQuery = `
        query FindPerformers($filter: FindFilterType, $performer_filter: PerformerFilterType) {
          findPerformers(filter: $filter, performer_filter: $performer_filter) {
            count
            performers {
              id
              name
              alias_list
              image_path
            }
          }
        }
      `;
      
      const variables = {
        filter: {
          per_page: 10,
          sort: "name",
          direction: "ASC"
        },
        performer_filter: {
          name: {
            value: name,
            modifier: "INCLUDES"
          }
        }
      };
      
      const response = await fetch(graphqlEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery, variables })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      }
      console.log('MutateGraphQL: Performer search response:', result);
      
      return result.data?.findPerformers?.performers || [];
    } catch (error) {
      console.error('MutateGraphQL: Error searching performers:', error);
      return [];
    }
  };

  const findPerformerByExactName = async (name: string) => {
    try {
      const performers = await searchPerformers(name);
      // Look for exact match first
      const exactMatch = performers.find((p: any) => 
        p.name?.toLowerCase() === name.toLowerCase()
      );
      
      if (exactMatch) {
        return exactMatch;
      }
      
      // Check aliases for exact match
      const aliasMatch = performers.find((p: any) => 
        p.alias_list?.some((alias: string) => alias.toLowerCase() === name.toLowerCase())
      );
      
      return aliasMatch || null;
    } catch (error) {
      console.error('MutateGraphQL: Error finding performer by exact name:', error);
      return null;
    }
  };

  const createPerformer = async (name: string, imageData?: string) => {
    try {
      console.log('MutateGraphQL: Creating new performer:', name);
      console.log('MutateGraphQL: Image data provided:', imageData ? `${imageData.substring(0, 50)}...` : 'null');
      
      const createMutation = `
        mutation PerformerCreate($input: PerformerCreateInput!) {
          performerCreate(input: $input) {
            id
            name
            alias_list
            image_path
          }
        }
      `;
      
      const input: any = {
        name: name,
        alias_list: []
      };
      
      // Re-enable image upload with proper format testing
      // Try multiple common GraphQL image field formats
      if (imageData && typeof imageData === 'string' && imageData.length > 100) {
        console.log('MutateGraphQL: Processing image data for performer creation');
        
        // Clean up the base64 data - remove any data URL prefix if present
        let cleanBase64 = imageData;
        if (imageData.startsWith('data:image/')) {
          cleanBase64 = imageData.split(',')[1];
        }
        
        // Validate it looks like base64 (starts with common base64 image headers)
        if (cleanBase64.startsWith('/9j/') || cleanBase64.startsWith('iVBOR') || cleanBase64.startsWith('R0lGOD')) {
          console.log('MutateGraphQL: Adding base64 image data to performer creation');
          
          // Try different field name formats that Stash might expect
          // Format 1: data URL format
          const dataUrl = `data:image/jpeg;base64,${cleanBase64}`;
          input.image = dataUrl;
          console.log('MutateGraphQL: Using data URL format for image');
          
        } else {
          console.log('MutateGraphQL: Image data does not appear to be valid base64 image:', cleanBase64.substring(0, 20));
        }
      } else if (imageData) {
        console.log('MutateGraphQL: Image data provided but skipping image upload for now:', typeof imageData, imageData?.length);
      }
      
      const variables = {
        input: input
      };
      
      const response = await fetch(graphqlEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: createMutation, variables })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      }
      console.log('MutateGraphQL: Performer creation response:', result);
      
      if (result.data?.performerCreate) {
        return result.data.performerCreate;
      } else {
        throw new Error('Failed to create performer - no data returned');
      }
    } catch (error) {
      console.error('MutateGraphQL: Error creating performer:', error);
      throw error;
    }
  };

  // =============================================================================
  // IMAGE PERFORMER ASSOCIATIONS
  // =============================================================================
  
  const getImagePerformers = async (imageId: string) => {
    try {
      console.log('MutateGraphQL: Getting performers for image:', imageId);
      
      const imageQuery = `
        query FindImage($id: ID!) {
          findImage(id: $id) {
            id
            performers {
              id
              name
              alias_list
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
      console.log('MutateGraphQL: Image performers response:', result);
      
      return result.data?.findImage?.performers || [];
    } catch (error) {
      console.error('MutateGraphQL: Error getting image performers:', error);
      return [];
    }
  };

  const addPerformerToImage = async (imageId: string, performerId: string) => {
    try {
      console.log('MutateGraphQL: Adding performer to image:', { imageId, performerId });
      
      // First get current performers
      const currentPerformers = await getImagePerformers(imageId);
      const currentPerformerIds = currentPerformers.map((p: any) => p.id);
      
      // Check if performer is already associated
      if (currentPerformerIds.includes(performerId)) {
        console.log('MutateGraphQL: Performer already associated with image');
        return { success: true, message: 'Performer already associated' };
      }
      
      // Add the new performer to the list
      const updatedPerformerIds = [...currentPerformerIds, performerId];
      
      const updateMutation = `
        mutation ImageUpdate($input: ImageUpdateInput!) {
          imageUpdate(input: $input) {
            id
            performers {
              id
              name
            }
          }
        }
      `;
      
      const variables = {
        input: {
          id: imageId,
          performer_ids: updatedPerformerIds
        }
      };
      
      const response = await fetch(graphqlEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: updateMutation, variables })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      };
      console.log('MutateGraphQL: Image update response:', result);
      
      if (result.data?.imageUpdate) {
        return { success: true, data: result.data.imageUpdate };
      } else {
        throw new Error('Failed to update image - no data returned');
      }
    } catch (error) {
      console.error('MutateGraphQL: Error adding performer to image:', error);
      return { success: false, error: error.message };
    }
  };

  const removePerformerFromImage = async (imageId: string, performerId: string) => {
    try {
      console.log('MutateGraphQL: Removing performer from image:', { imageId, performerId });
      
      // First get current performers
      const currentPerformers = await getImagePerformers(imageId);
      const currentPerformerIds = currentPerformers.map((p: any) => p.id);
      
      // Remove the performer from the list
      const updatedPerformerIds = currentPerformerIds.filter((id: string) => id !== performerId);
      
      const updateMutation = `
        mutation ImageUpdate($input: ImageUpdateInput!) {
          imageUpdate(input: $input) {
            id
            performers {
              id
              name
            }
          }
        }
      `;
      
      const variables = {
        input: {
          id: imageId,
          performer_ids: updatedPerformerIds
        }
      };
      
      const response = await fetch(graphqlEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: updateMutation, variables })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      };
      console.log('MutateGraphQL: Image update response:', result);
      
      if (result.data?.imageUpdate) {
        return { success: true, data: result.data.imageUpdate };
      } else {
        throw new Error('Failed to update image - no data returned');
      }
    } catch (error) {
      console.error('MutateGraphQL: Error removing performer from image:', error);
      return { success: false, error: error.message };
    }
  };

  // =============================================================================
  // HIGH-LEVEL PERFORMER MANAGEMENT
  // =============================================================================
  
  const findOrCreatePerformer = async (name: string, imageData?: string) => {
    try {
      console.log('MutateGraphQL: Find or create performer:', name);
      
      // First try to find existing performer
      const existingPerformer = await findPerformerByExactName(name);
      
      if (existingPerformer) {
        console.log('MutateGraphQL: Found existing performer:', existingPerformer);
        return { performer: existingPerformer, created: false };
      }
      
      // Create new performer if not found
      console.log('MutateGraphQL: Creating new performer:', name);
      const newPerformer = await createPerformer(name, imageData);
      
      return { performer: newPerformer, created: true };
    } catch (error) {
      console.error('MutateGraphQL: Error in findOrCreatePerformer:', error);
      throw error;
    }
  };

  const associatePerformerWithEntity = async (
    performerName: string, 
    entityType: string, 
    entityId: string,
    performerImageData?: string
  ) => {
    try {
      console.log('MutateGraphQL: Associating performer with entity:', {
        performerName,
        entityType,
        entityId
      });
      
      console.log('MutateGraphQL: associatePerformerWithEntity called with:', {
        performerName,
        entityType,
        entityId,
        hasImageData: !!performerImageData,
        imageDataPreview: performerImageData ? `${performerImageData.substring(0, 50)}...` : null
      });
      
      // Find or create the performer
      const { performer, created } = await findOrCreatePerformer(performerName, performerImageData);
      
      if (!performer || !performer.id) {
        throw new Error('Failed to find or create performer');
      }
      
      // Currently only support images, but can be extended for scenes/galleries
      if (entityType.toLowerCase() === 'image') {
        const result = await addPerformerToImage(entityId, performer.id);
        
        return {
          success: result.success,
          performer: performer,
          created: created,
          associated: result.success,
          message: created 
            ? `Created and associated performer "${performerName}"` 
            : `Associated existing performer "${performerName}"`,
          error: result.error
        };
      } else {
        throw new Error(`Entity type "${entityType}" not yet supported`);
      }
    } catch (error) {
      console.error('MutateGraphQL: Error associating performer with entity:', error);
      return {
        success: false,
        error: error.message || 'Unknown error occurred'
      };
    }
  };

  // =============================================================================
  // RETURN API
  // =============================================================================
  
  return {
    searchPerformers,
    findPerformerByExactName,
    createPerformer,
    getImagePerformers,
    addPerformerToImage,
    removePerformerFromImage,
    findOrCreatePerformer,
    associatePerformerWithEntity
  };
};

// Expose globally for plugin usage
(window as any).MutateGraphQL = MutateGraphQL;

export default MutateGraphQL;