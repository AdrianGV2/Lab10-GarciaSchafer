import { useEffect, useRef } from 'react';

const PythonEditor = ({ source, onSourceChange, output, running }) => {
  const consoleRef = useRef(null);

  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [output]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <textarea
        value={source}
        onChange={(e) => onSourceChange(e.target.value)}
        spellCheck={false}
        style={{
          flex: 1,
          resize: 'none',
          backgroundColor: '#0d1117',
          color: '#c9d1d9',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '12px',
          fontFamily: 'Consolas, "Courier New", monospace',
          fontSize: '0.95rem',
          lineHeight: 1.5,
          outline: 'none'
        }}
      />

      <div
        ref={consoleRef}
        style={{
          height: '30%',
          minHeight: '120px',
          overflowY: 'auto',
          backgroundColor: '#010409',
          color: '#8b949e',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '10px 12px',
          fontFamily: 'Consolas, "Courier New", monospace',
          fontSize: '0.85rem',
          whiteSpace: 'pre-wrap'
        }}
      >
        <div style={{ color: '#58a6ff', marginBottom: '6px' }}>
          Consola {running ? '· ejecutando…' : ''}
        </div>
        {output.length === 0
          ? <span style={{ opacity: 0.6 }}>Sin salida todavía.</span>
          : output.map((line, i) => <div key={i}>{line}</div>)}
      </div>
    </div>
  );
};

export default PythonEditor;
