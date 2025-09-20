// =============================================================================
// New AI Button Integration - Test Integration
// =============================================================================

(function () {
  const PluginApi = (window as any).PluginApi;
  const React = PluginApi.React;
  
  // Add the new button to the main navigation for testing
  PluginApi.patch.before('MainNavBar.UtilityItems', function (props: any) {
    // Check if NewAIButton is available
    const NewAIButton = (window as any).NewAIButton;
    if (!NewAIButton) {
      console.warn('NewAIButton not available yet, skipping integration');
      return [{children: props.children}];
    }

    // Don't pass context - let NewAIButton auto-detect the page
    return [
      {
        children: React.createElement('div', {
          style: { display: 'flex', alignItems: 'center' }
        }, [
          props.children,
          React.createElement('div', {
            key: 'new-ai-button-wrapper',
            style: { marginRight: '8px' }
          }, React.createElement(NewAIButton, {}))
        ])
      }
    ];
  });

  console.log('🚀 New AI Button integration loaded');
})();