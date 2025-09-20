// =============================================================================
// SVG Icons Utility - Clean icon loading system
// =============================================================================

// StashAI SVG Icon (from StashAI.svg)
export const StashAISVG = `<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="24" height="24" viewBox="0 0 512 512" style="shape-rendering:geometricPrecision; text-rendering:geometricPrecision; image-rendering:optimizeQuality; fill-rule:evenodd; clip-rule:evenodd" xmlns:xlink="http://www.w3.org/1999/xlink">
<g><path style="opacity:0.96" fill="currentColor" d="M 368.5,31.5 C 370.167,31.5 371.833,31.5 373.5,31.5C 377.124,47.4123 383.957,61.7456 394,74.5C 407.555,87.0308 423.388,95.5308 441.5,100C 442.833,101.333 442.833,102.667 441.5,104C 405.409,112.424 382.909,134.591 374,170.5C 373.121,173.346 371.454,174.013 369,172.5C 364.745,155.655 357.079,140.655 346,127.5C 333.21,116.436 318.543,108.77 302,104.5C 298.88,102.163 299.38,100.33 303.5,99C 328.118,93.6327 346.618,80.1327 359,58.5C 362.671,49.6534 365.837,40.6534 368.5,31.5 Z"/></g>
<g><path style="opacity:0.979" fill="currentColor" d="M 206.5,115.5 C 209.368,115.085 211.535,116.085 213,118.5C 219.296,138.389 226.962,157.722 236,176.5C 250.915,200.888 271.081,219.722 296.5,233C 313.345,239.727 330.345,246.06 347.5,252C 349.257,255.732 348.257,258.399 344.5,260C 327.599,265.744 310.933,272.078 294.5,279C 261.426,296.747 238.259,323.247 225,358.5C 221,369.833 217,381.167 213,392.5C 210.679,395.917 208.012,396.25 205,393.5C 198.566,372.863 190.566,352.863 181,333.5C 163.119,304.623 138.286,284.123 106.5,272C 95.1667,268 83.8333,264 72.5,260C 67.1667,257 67.1667,254 72.5,251C 91.6411,244.842 110.308,237.509 128.5,229C 156.047,213.119 176.214,190.619 189,161.5C 194.59,146.001 200.424,130.668 206.5,115.5 Z"/></g>
<g><path style="opacity:0.96" fill="currentColor" d="M 369.5,337.5 C 370.822,337.33 371.989,337.663 373,338.5C 381.424,374.591 403.591,397.091 439.5,406C 442.346,406.879 443.013,408.546 441.5,411C 423.388,415.469 407.555,423.969 394,436.5C 383.957,449.254 377.124,463.588 373.5,479.5C 371.833,479.5 370.167,479.5 368.5,479.5C 364.86,463.556 358.027,449.223 348,436.5C 335.628,424.06 320.794,415.893 303.5,412C 299.38,410.67 298.88,408.837 302,406.5C 318.543,402.23 333.21,394.564 346,383.5C 349.716,379.452 353.05,375.118 356,370.5C 361.387,359.833 365.887,348.833 369.5,337.5 Z"/></g>
</svg>`;

// Utility function to create SVG data URLs
export function createSVGDataURL(svgString: string): string {
  return `data:image/svg+xml;base64,${btoa(svgString)}`;
}

// Utility function to create inline SVG React element
export function createInlineSVG(svgString: string, props?: any): any {
  const React = (window as any).PluginApi?.React;
  if (!React) return null;

  // Parse the SVG string to extract attributes and create React element
  const parser = new DOMParser();
  const svgDoc = parser.parseFromString(svgString, 'image/svg+xml');
  const svgElement = svgDoc.querySelector('svg');
  
  if (!svgElement) return null;

  // Extract SVG attributes
  const svgProps: any = {
    xmlns: svgElement.getAttribute('xmlns') || 'http://www.w3.org/2000/svg',
    width: svgElement.getAttribute('width') || '24',
    height: svgElement.getAttribute('height') || '24', 
    viewBox: svgElement.getAttribute('viewBox') || '0 0 24 24',
    ...props
  };

  // Convert child nodes to React elements
  const children: any[] = [];
  Array.from(svgElement.children).forEach((child, index) => {
    if (child.tagName === 'g') {
      const paths: any[] = [];
      Array.from(child.children).forEach((pathChild, pathIndex) => {
        if (pathChild.tagName === 'path') {
          paths.push(React.createElement('path', {
            key: `path-${index}-${pathIndex}`,
            style: pathChild.getAttribute('style') ? 
              pathChild.getAttribute('style').split(';').reduce((acc: any, style: string) => {
                const [prop, value] = style.split(':');
                if (prop && value) {
                  const camelProp = prop.trim().replace(/-([a-z])/g, (g) => g[1].toUpperCase());
                  acc[camelProp] = value.trim();
                }
                return acc;
              }, {}) : {},
            fill: pathChild.getAttribute('fill') || 'currentColor',
            d: pathChild.getAttribute('d')
          }));
        }
      });
      children.push(React.createElement('g', { key: `g-${index}` }, paths));
    }
  });

  return React.createElement('svg', svgProps, children);
}

// Make icons available globally
(window as any).AIOverhaulSVGIcons = {
  StashAI: StashAISVG,
  createDataURL: createSVGDataURL,
  createInline: createInlineSVG
};