export const styles = {
  appContainer: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#0d1117',
    color: '#c9d1d9',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    overflow: 'hidden'
  },
  header: {
    height: '60px',
    backgroundColor: '#161b22',
    borderBottom: '1px solid #30363d',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 20px',
  },
  logoContainer: {
    display: 'flex',
    alignItems: 'center',
  },
  logoIcon: {
    fontSize: '1.5rem',
    color: '#58a6ff',
    marginRight: '10px',
  },
  title: {
    margin: 0,
    fontSize: '1.2rem',
    fontWeight: '600',
    color: '#c9d1d9'
  },
  scenarioSelector: {
    display: 'flex',
    alignItems: 'center',
    backgroundColor: '#0d1117',
    padding: '5px 15px',
    borderRadius: '20px',
    border: '1px solid #30363d'
  },
  scenarioLabel: {
    fontSize: '0.85rem',
    marginRight: '10px',
    color: '#8b949e'
  },
  select: {
    backgroundColor: 'transparent',
    border: 'none',
    color: '#58a6ff',
    fontWeight: 'bold',
    outline: 'none',
    cursor: 'pointer'
  },
  mainContent: {
    display: 'flex',
    flex: 1,
    padding: '20px',
    gap: '20px',
    overflow: 'hidden'
  },
  leftCol: {
    width: '40%',
    minWidth: '400px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px'
  },
  videoContainer: {
    flex: 1,
    backgroundColor: '#000',
    borderRadius: '12px',
    overflow: 'hidden',
    position: 'relative',
    border: '1px solid #30363d',
    boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
  },
  videoOverlay: {
    position: 'absolute',
    top: '10px',
    left: '10px',
    backgroundColor: 'rgba(255,0,0,0.7)',
    color: 'white',
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '0.75rem',
    fontWeight: 'bold',
    zIndex: 10,
    letterSpacing: '1px'
  },
  videoImg: {
    width: '100%',
    height: '100%',
    objectFit: 'contain'
  },
  cameraControls: {
    position: 'absolute',
    bottom: '15px',
    right: '15px',
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
    backgroundColor: 'rgba(22, 27, 34, 0.8)',
    padding: '8px',
    borderRadius: '8px',
    border: '1px solid #30363d',
    zIndex: 10,
    backdropFilter: 'blur(4px)'
  },
  cameraBtnRow: {
    display: 'flex',
    justifyContent: 'center',
    gap: '5px'
  },
  cameraBtn: {
    backgroundColor: '#21262d',
    border: '1px solid #30363d',
    color: '#c9d1d9',
    borderRadius: '6px',
    width: '32px',
    height: '32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    transition: 'background-color 0.2s'
  },
  missionContainer: {
    height: '35%',
  },
  rightCol: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#161b22',
    borderRadius: '12px',
    border: '1px solid #30363d',
    overflow: 'hidden',
    boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
  },
  editorHeader: {
    padding: '15px 20px',
    borderBottom: '1px solid #30363d',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#161b22'
  },
  editorTitle: {
    margin: 0,
    fontSize: '1.1rem',
    color: '#8b949e',
    fontWeight: '500'
  },
  editorActions: {
    display: 'flex',
    gap: '10px'
  },
  actionBtn: {
    display: 'flex',
    alignItems: 'center',
    padding: '8px 16px',
    border: 'none',
    borderRadius: '6px',
    color: 'white',
    fontWeight: 'bold',
    cursor: 'pointer',
    fontSize: '0.9rem',
    transition: 'transform 0.1s ease, filter 0.2s ease',
  },
  blocklyWrapper: {
    flex: 1,
    position: 'relative',
    backgroundColor: '#1e1e1e'
  },
  homeContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    width: '100vw',
    backgroundColor: '#0d1117',
    fontFamily: "'Inter', sans-serif"
  },
  homeBox: {
    backgroundColor: '#161b22',
    padding: '40px',
    borderRadius: '16px',
    border: '1px solid #30363d',
    textAlign: 'center',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
    maxWidth: '800px',
    width: '90%'
  },
  scenarioGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '15px',
    marginTop: '20px'
  },
  scenarioCard: {
    backgroundColor: '#21262d',
    border: '1px solid #30363d',
    borderRadius: '12px',
    padding: '20px',
    cursor: 'pointer',
    transition: 'transform 0.2s, borderColor 0.2s',
  },
  cardHeader: {
    color: '#58a6ff',
    fontWeight: 'bold',
    fontSize: '1.2rem',
    marginBottom: '10px'
  },
  cardBody: {
    color: '#c9d1d9',
    fontSize: '0.9rem'
  },
  loadingContainer: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    width: '100vw',
    backgroundColor: '#0d1117',
    fontFamily: "'Inter', sans-serif"
  },
  spinner: {
    width: '60px',
    height: '60px',
    border: '6px solid #161b22',
    borderTop: '6px solid #58a6ff',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite'
  }
};

const addHoverStyles = () => {
  if (typeof document !== 'undefined') {
    const style = document.createElement('style');
    style.innerHTML = `
      div[style*="cursor: pointer"]:hover {
        border-color: #58a6ff !important;
        transform: translateY(-2px);
      }
    `;
    document.head.appendChild(style);
  }
};
addHoverStyles();
