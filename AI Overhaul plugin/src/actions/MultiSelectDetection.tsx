// =============================================================================
// Multi-Select Detection - Context detection for batch operations
// =============================================================================

export interface MultiSelectContext {
  selectionType: 'images' | 'scenes' | 'galleries' | 'performers';
  selectedItems: string[];
  count: number;
}

// Detect multi-select context from DOM
export const detectMultiSelectContext = (): MultiSelectContext | null => {
  try {
    const pathname = window.location.pathname;
    let selectionType: 'images' | 'scenes' | 'galleries' | 'performers' = 'images';
    
    if (pathname.includes('/scenes')) {
      selectionType = 'scenes';
    } else if (pathname.includes('/performers')) {
      selectionType = 'performers';
    } else if (pathname.includes('/galleries')) {
      selectionType = 'galleries';
    } else if (pathname.includes('/images')) {
      selectionType = 'images';
    }

    const selectedCheckboxes = document.querySelectorAll(
      '.grid-card .card-check:checked, .scene-card .card-check:checked, .performer-card .card-check:checked, .gallery-card .card-check:checked'
    );
    
    if (selectedCheckboxes.length <= 1) {
      return null;
    }

    const selectedItems: string[] = [];
    selectedCheckboxes.forEach((checkbox) => {
      const card = checkbox.closest('.grid-card, .scene-card, .performer-card, .gallery-card');
      if (card) {
        const link = card.querySelector('a[href]');
        if (link) {
          const match = (link as HTMLAnchorElement).href.match(/\/(?:images|scenes|performers|galleries)\/(\d+)/);
          if (match) {
            selectedItems.push(match[1]);
          }
        }
      }
    });

    if (selectedItems.length <= 1) {
      return null;
    }

    console.log(`🎯 Multi-select detected: ${selectedItems.length} ${selectionType} selected`);

    return {
      selectionType,
      selectedItems,
      count: selectedItems.length
    };

  } catch (error) {
    console.error('Error detecting multi-select context:', error);
    return null;
  }
};