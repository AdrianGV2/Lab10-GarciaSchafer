import React from 'react';
import { FaCheckCircle, FaRegCircle, FaFlagCheckered } from 'react-icons/fa';

const MissionObjectives = ({ scenario, telemetry }) => {
  if (!scenario || !scenario.objectives || scenario.objectives.length === 0) {
    return (
      <div style={styles.container}>
        <span style={styles.text}><FaFlagCheckered style={{ marginRight: '5px' }} /> Modo Libre</span>
      </div>
    );
  }

  const checkObjective = (obj) => {
    if (!telemetry || !telemetry.entities) return false;

    // Evaluador de Misiones basado en reglas (Phase 4 spec)
    if (obj.validator === "push_object") {
      // Leemos todos los objetos de la escena independientemente de su nombre o figura
      const objectNames = Object.keys(telemetry.entities);
      for (const name of objectNames) {
        const pos = telemetry.entities[name];
        // Objetivo cumplido si el objeto cae de la mesa (Z negativo) o se empuja fuera del área.
        if (pos[2] < -0.05 || Math.abs(pos[0]) > 0.35 || Math.abs(pos[1]) > 0.35) {
          return true;
        }
      }
    }
    return false;
  };

  const allCompleted = scenario.objectives.every(obj => checkObjective(obj));

  return (
    <div style={{ ...styles.container, borderColor: allCompleted ? '#4caf50' : '#30363d' }}>
      <span style={{ ...styles.title, color: allCompleted ? '#4caf50' : '#c9d1d9' }}>
        <FaFlagCheckered style={{ marginRight: '8px' }} />
        {allCompleted ? "¡Misión Completada!" : "Objetivos:"}
      </span>
      <div style={styles.list}>
        {scenario.objectives.map(obj => {
          const isDone = checkObjective(obj);
          return (
            <span key={obj.id} style={{ ...styles.item, color: isDone ? '#4caf50' : '#8b949e' }}>
              {isDone ? <FaCheckCircle style={styles.icon} /> : <FaRegCircle style={styles.icon} />}
              <span style={{ textDecoration: isDone ? 'line-through' : 'none' }}>{obj.description}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
};

const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    backgroundColor: '#161b22',
    padding: '5px 15px',
    borderRadius: '8px',
    border: '1px solid #30363d',
    gap: '15px'
  },
  title: {
    fontWeight: 'bold',
    display: 'flex',
    alignItems: 'center',
    fontSize: '0.95rem'
  },
  list: {
    display: 'flex',
    gap: '15px',
    alignItems: 'center'
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    fontSize: '0.9rem'
  },
  icon: {
    marginRight: '5px'
  },
  text: {
    color: '#8b949e',
    fontSize: '0.9rem',
    display: 'flex',
    alignItems: 'center'
  }
};

export default MissionObjectives;
