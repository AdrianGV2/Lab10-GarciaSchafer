import React, { useState } from 'react';

const MissionPanel = ({ telemetry }) => {
  const [viewMode, setViewMode] = useState("positions"); // "positions" or "joints"

  const formatPos = (pos) => {
    if (!pos || pos.length !== 3) return "-";
    const x = Math.round(pos[0] * 100);
    const y = Math.round(pos[1] * 100);
    const z = Math.round(pos[2] * 100);
    return `X: ${x} Y: ${y} Z: ${z}`;
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h4 style={styles.title}>
          {viewMode === "positions" ? "Posiciones en Vivo" : "Ángulos de Motores"}
        </h4>
        <button 
          style={styles.toggleBtn} 
          onClick={() => setViewMode(viewMode === "positions" ? "joints" : "positions")}
        >
          {viewMode === "positions" ? "Ver Grados" : "Ver Coordenadas"}
        </button>
      </div>
      
      {viewMode === "positions" ? (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Objeto</th>
              <th style={styles.th}>Coordenadas (cm)</th>
            </tr>
          </thead>
          <tbody>
            {telemetry?.robot_end_effectors && Object.entries(telemetry.robot_end_effectors).map(([name, pos]) => (
              <tr key={`robot-${name}`}>
                <td style={{ ...styles.td, fontWeight: 'bold', color: '#58a6ff' }}>🤖 Garra de {name}</td>
                <td style={styles.td}>{formatPos(pos)}</td>
              </tr>
            ))}
            {telemetry?.entities && Object.entries(telemetry.entities).map(([name, pos]) => (
              <tr key={name}>
                <td style={styles.td}>📦 {name}</td>
                <td style={styles.td}>{formatPos(pos)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Robot</th>
              <th style={styles.th}>Estado de Motores (J1 | Z | J3 | J4)</th>
            </tr>
          </thead>
          <tbody>
            {telemetry?.robot_joints && Object.entries(telemetry.robot_joints).map(([name, joints]) => (
              <tr key={`joints-${name}`}>
                <td style={{ ...styles.td, fontWeight: 'bold', color: '#58a6ff' }}>🤖 {name}</td>
                <td style={styles.td}>
                  {joints ? `J1: ${joints[0]}° | Z: ${joints[1]}cm | J3: ${joints[2]}° | J4: ${joints[3]}°` : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: '#1e1e1e', // Dark theme matching Blockly
    borderRadius: '8px',
    padding: '15px',
    border: '2px solid #333',
    height: '100%',
    overflowY: 'auto'
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '15px'
  },
  title: {
    color: '#61dafb',
    margin: '0',
    fontSize: '1.1rem',
    textTransform: 'uppercase',
    letterSpacing: '1px'
  },
  toggleBtn: {
    backgroundColor: '#30363d',
    color: '#c9d1d9',
    border: '1px solid #8b949e',
    borderRadius: '4px',
    padding: '4px 8px',
    fontSize: '0.8rem',
    cursor: 'pointer',
    transition: 'background 0.2s',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '0.9rem',
    color: '#c9d1d9'
  },
  th: {
    textAlign: 'left',
    padding: '8px',
    borderBottom: '1px solid #30363d',
    color: '#8b949e',
    fontWeight: 'normal'
  },
  td: {
    padding: '8px',
    borderBottom: '1px solid #21262d'
  }
};

export default MissionPanel;

