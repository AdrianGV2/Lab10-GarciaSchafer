import { useState, useEffect, useRef } from 'react';
import BlocklyEditor from './components/BlocklyEditor';
import PythonEditor from './components/PythonEditor';
import MissionPanel from './components/MissionPanel';
import MissionObjectives from './components/MissionObjectives';
import { FaPlay, FaStop, FaRobot, FaRedo, FaSearchPlus, FaSearchMinus, FaArrowUp, FaArrowDown, FaArrowLeft, FaArrowRight } from 'react-icons/fa';
import { styles } from './AppStyles';
import { api, wsUrl } from './api';

function App() {
  const [currentScreen, setCurrentScreen] = useState("home");
  const [telemetry, setTelemetry] = useState(null);
  const [scenarios, setScenarios] = useState([]);
  const [activeScenarioPath, setActiveScenarioPath] = useState("");
  const activeScenarioRef = useRef("");
  const [compiledCommands, setCompiledCommands] = useState([]);

  const [editorMode, setEditorMode] = useState("blockly");
  const [pythonSource, setPythonSource] = useState(
    'from manito_api import ManitoArm\n\nbrazo = ManitoArm()\n\nbrazo.home()\n'
  );
  const [scriptOutput, setScriptOutput] = useState([]);
  const [scriptRunning, setScriptRunning] = useState(false);
  const scriptCursorRef = useRef(0);

  useEffect(() => {
    const fetchScenarios = async () => {
      try {
        const res = await fetch(api("/api/v1/scenarios"));
        const data = await res.json();
        if (data.status === "success") {
          setScenarios(data.scenarios);
          if (data.scenarios.length > 0) {
            setActiveScenarioPath(data.scenarios[0].path);
          }
        }
      } catch (err) {
        console.error("Error fetching scenarios:", err);
      }
    };
    fetchScenarios();
  }, []);

  // Telemetry WS
  useEffect(() => {
    const ws = new WebSocket(wsUrl("/api/v1/ws/state"));
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.current_block) {
          console.log("App.jsx recibe telemetry.current_block:", data.current_block);
        }
        setTelemetry(data);

        // Guardrail Interceptor
        if (data.lifecycle && data.lifecycle.status === "failed" && !abortExecutionRef.current) {
          abortExecutionRef.current = true;
          const reasonMsg = data.lifecycle.reason === "max_steps_reached" 
            ? "Límite máximo de comandos excedido (posible bucle infinito)." 
            : "Tiempo máximo de ejecución excedido.";
          alert(`Ejecución abortada por seguridad:\n${reasonMsg}`);
        }
        setCurrentScreen(prevScreen => {
          if (prevScreen === "loading" && data.status === "running") {
            if (!data.scenario_path || data.scenario_path === activeScenarioRef.current) {
              return "simulator";
            }
          }
          return prevScreen;
        });
      } catch (err) {
        console.error("Error parseando telemetría WS:", err);
      }
    };
    return () => ws.close();
  }, []);

  const enviarComando = async (comando) => {
    let retries = 0;
    while (!abortExecutionRef.current || comando.action === "stop_program" || comando.action === "reset" || comando.action.startsWith("camera_")) {
      try {
        const response = await fetch(api("/api/v1/command"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(comando)
        });
        
        if (response.status === 429) {
          // Buzón lleno, esperar medio segundo y reintentar
          await new Promise(resolve => setTimeout(resolve, 500));
          retries++;
          if (retries > 60) {
            console.error("Timeout esperando espacio en la cola (buzón lleno prolongado).");
            break;
          }
          continue;
        }
        
        break; // Éxito o error distinto de 429
      } catch (error) {
        console.error("Error conectando al simulador:", error);
        break;
      }
    }
  };

  const selectScenarioAndLoad = async (scenarioPath) => {
    setActiveScenarioPath(scenarioPath);
    activeScenarioRef.current = scenarioPath;
    setCurrentScreen("loading");
    await fetch(api("/api/v1/command"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "reload_scenario", scenario: scenarioPath })
    });
  };

  const handleScenarioChange = async (newPath) => {
    setActiveScenarioPath(newPath);
    activeScenarioRef.current = newPath;
    setCurrentScreen("loading");
    await enviarComando({ action: "reload_scenario", scenario: newPath });
  };

  const returnToHome = () => {
    setCurrentScreen("home");
  };

  const handleCompile = (commands) => {
    setCompiledCommands(prev => {
      const prevStr = JSON.stringify(prev);
      const newStr = JSON.stringify(commands);
      return prevStr === newStr ? prev : commands;
    });
  };

  const abortExecutionRef = useRef(false);

  const executeProgram = async () => {
    if (compiledCommands.length === 0) return;
    // console.log("Comandos a ejecutar (tienen block_id?):", compiledCommands);

    // Validación
    const maxReach = 36;
    for (let i = 0; i < compiledCommands.length; i++) {
      const cmd = compiledCommands[i];
      if (cmd.action === "move_to") {
        const x_cm = cmd.x * 100;
        const y_cm = cmd.y * 100;
        const distance = Math.sqrt(x_cm * x_cm + y_cm * y_cm);
        if (distance > maxReach) {
          alert(`Error en paso ${i + 1}: La coordenada (X:${x_cm}, Y:${y_cm}) está fuera del alcance máximo del robot (${maxReach} cm).\n
            Distancia solicitada: ${distance.toFixed(1)} cm. Ejecución cancelada.`);
          return;
        }
      }
    }

    abortExecutionRef.current = false;

    for (const cmd of compiledCommands) {
      if (abortExecutionRef.current) break;
      await enviarComando(cmd);
    }
  };

  // Mientras el script corre, arrastramos su salida hacia la consola del editor.
  useEffect(() => {
    if (!scriptRunning) return;

    const intervalId = setInterval(async () => {
      try {
        const res = await fetch(
          api(`/api/v1/script/output?since=${scriptCursorRef.current}`)
        );
        const data = await res.json();
        scriptCursorRef.current = data.next_index;
        if (data.lines.length > 0) {
          setScriptOutput(prev => [...prev, ...data.lines]);
        }
        if (data.status !== "running") {
          setScriptRunning(false);
        }
      } catch (err) {
        console.error("Error consultando la salida del script:", err);
      }
    }, 400);

    return () => clearInterval(intervalId);
  }, [scriptRunning]);

  const runPythonProgram = async () => {
    setScriptOutput([]);
    scriptCursorRef.current = 0;
    abortExecutionRef.current = false;

    try {
      const res = await fetch(api("/api/v1/script/run"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: pythonSource })
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        alert(`No se pudo iniciar el script: ${detail.detail || res.status}`);
        return;
      }
      setScriptRunning(true);
    } catch (err) {
      console.error("Error iniciando el script:", err);
      alert("No se pudo conectar con el simulador para ejecutar el script.");
    }
  };

  const runProgram = () => {
    if (editorMode === "python") {
      runPythonProgram();
    } else {
      executeProgram();
    }
  };

  // Blockly se queda montado al cambiar de pestaña para no perder el workspace,
  // pero necesita recalcular su tamaño cuando vuelve a ser visible.
  const switchEditor = (mode) => {
    setEditorMode(mode);
    if (mode === "blockly") {
      setTimeout(() => window.dispatchEvent(new Event('resize')), 0);
    }
  };

  const sendBlocksToPython = (code) => {
    setPythonSource(code);
    setEditorMode("python");
  };

  const stopProgram = () => {
    abortExecutionRef.current = true;
    enviarComando({ action: "stop_program" });
    fetch(api("/api/v1/script/stop"), { method: "POST" })
      .catch(err => console.error("Error deteniendo el script:", err));
  };

  const resetScenario = () => {
    abortExecutionRef.current = true;
    enviarComando({ action: "reset" });
  };

  const handleCamera = (action, value) => {
    if (action === "camera_zoom") enviarComando({ action, zoom: value });
    if (action === "camera_lift") enviarComando({ action, z: value });
    if (action === "camera_lateral") enviarComando({ action, y: value });
  };

  const activeScenarioObj = scenarios.find(s => s.path === activeScenarioPath);

  if (currentScreen === "home") {
    return (
      <div style={styles.homeContainer}>
        <div style={styles.homeBox}>
          <FaRobot style={{ fontSize: '4rem', color: '#58a6ff', marginBottom: '1rem' }} />
          <h1 style={{ color: '#fff', fontSize: '2.5rem', marginBottom: '2rem' }}>Manito Genesis Simulator</h1>
          
          <div style={{ display: 'flex', justifyContent: 'center', width: '100%' }}>
            <button 
              style={{ 
                ...styles.actionBtn, 
                backgroundColor: '#2ea043', 
                fontSize: '1.5rem', 
                padding: '15px 40px', 
                marginTop: '1rem',
                opacity: scenarios.length === 0 ? 0.5 : 1,
                cursor: scenarios.length === 0 ? 'not-allowed' : 'pointer'
              }}
              disabled={scenarios.length === 0}
              onClick={() => selectScenarioAndLoad(scenarios[0]?.path)}
            >
              <FaPlay style={{ marginRight: '10px' }} /> Empezar
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (currentScreen === "loading") {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.spinner}></div>
        <h2 style={{ color: '#58a6ff', marginTop: '2rem' }}>Compilando...</h2>
        <p style={{ color: '#8b949e', marginTop: '1rem' }}>
          Reconstruyendo Misión {scenarios.findIndex(s => s.path === activeScenarioPath) + 1 || 1}
        </p>
        <style>{`
          @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        `}</style>
      </div>
    );
  }

  return (
    <div style={styles.appContainer}>
      {/* HEADER */}
      <header style={styles.header}>
        <div style={styles.logoContainer}>
          <button onClick={returnToHome} style={{ ...styles.actionBtn, backgroundColor: 'transparent', border: '1px solid #58a6ff', color: '#58a6ff', marginRight: '15px' }}>
            ⬅ Volver
          </button>
          <FaRobot style={styles.logoIcon} />
          <h1 style={styles.title}>Manito Genesis Simulator</h1>
        </div>

        {/* OBJETIVOS */}
        <div style={{ flex: 1, display: 'flex', justifyContent: 'center', padding: '0 20px' }}>
          <MissionObjectives scenario={activeScenarioObj} telemetry={telemetry} />
        </div>

        <div style={styles.scenarioSelector}>
          <label style={styles.scenarioLabel}>Misión:</label>
          <div style={{ display: 'flex', gap: '8px', marginLeft: '10px' }}>
            {scenarios.map((sc, idx) => {
              const isActive = sc.path === activeScenarioPath;
              return (
                <button
                  key={idx}
                  onClick={() => handleScenarioChange(sc.path)}
                  disabled={isActive}
                  style={{
                    width: '35px',
                    height: '35px',
                    borderRadius: '50%',
                    border: 'none',
                    backgroundColor: isActive ? '#d29922' : '#21262d',
                    color: isActive ? '#ffffff' : '#c9d1d9',
                    fontWeight: 'bold',
                    fontSize: '1rem',
                    cursor: isActive ? 'default' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.2s',
                    boxShadow: isActive ? '0 0 10px rgba(210, 153, 34, 0.5)' : '0 0 5px rgba(0,0,0,0.5)'
                  }}
                  title={`Cargar Misión ${idx + 1}`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <div style={styles.mainContent}>

        {/* Video & Mission Panel */}
        <div style={styles.leftCol}>
          <div style={styles.videoContainer}>
            <img
              src={api("/api/v1/video_feed")}
              alt="Live Simulation"
              style={styles.videoImg}
            />
            {/* Controles de Cámara */}
            <div style={styles.cameraControls}>
              <div style={styles.cameraBtnRow}>
                <button style={styles.cameraBtn} onClick={() => handleCamera("camera_lift", 0.1)} title="Subir Cámara">
                  <FaArrowUp />
                </button>
              </div>
              <div style={styles.cameraBtnRow}>
                <button style={styles.cameraBtn} onClick={() => handleCamera("camera_lateral", -0.1)} title="Mover Izquierda">
                  <FaArrowLeft />
                </button>
                <button style={styles.cameraBtn} onClick={() => handleCamera("camera_lift", -0.1)} title="Bajar Cámara">
                  <FaArrowDown />
                </button>
                <button style={styles.cameraBtn} onClick={() => handleCamera("camera_lateral", 0.1)} title="Mover Derecha">
                  <FaArrowRight />
                </button>
              </div>
              <div style={styles.cameraBtnRow} style={{ marginTop: '5px', gap: '5px', display: 'flex', justifyContent: 'center' }}>
                <button style={styles.cameraBtn} onClick={() => handleCamera("camera_zoom", 0.2)} title="Zoom In">
                  <FaSearchPlus />
                </button>
                <button style={styles.cameraBtn} onClick={() => handleCamera("camera_zoom", -0.2)} title="Zoom Out">
                  <FaSearchMinus />
                </button>
              </div>
            </div>
          </div>

          <div style={styles.missionContainer}>
            <MissionPanel telemetry={telemetry} />
          </div>
        </div>

        {/* Blockly Editor & Controls */}
        <div style={styles.rightCol}>
          <div style={styles.editorHeader}>
            <div style={{ display: 'flex', gap: '6px' }}>
              {[['blockly', 'Blockly'], ['python', 'Python']].map(([mode, label]) => (
                <button
                  key={mode}
                  onClick={() => switchEditor(mode)}
                  style={{
                    ...styles.actionBtn,
                    backgroundColor: editorMode === mode ? '#30363d' : 'transparent',
                    border: `1px solid ${editorMode === mode ? '#58a6ff' : '#30363d'}`,
                    color: editorMode === mode ? '#58a6ff' : '#8b949e',
                    fontWeight: 'bold'
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <div style={styles.editorActions}>
              <button onClick={resetScenario} style={{ ...styles.actionBtn, backgroundColor: '#1f6feb' }}>
                <FaRedo style={{ marginRight: '5px' }} /> Reiniciar Escenario
              </button>
              <button onClick={stopProgram} style={{ ...styles.actionBtn, backgroundColor: '#d32f2f' }}>
                <FaStop style={{ marginRight: '5px' }} /> Detener
              </button>
              <button
                onClick={runProgram}
                disabled={scriptRunning}
                style={{
                  ...styles.actionBtn,
                  backgroundColor: '#2e7d32',
                  opacity: scriptRunning ? 0.5 : 1,
                  cursor: scriptRunning ? 'not-allowed' : 'pointer'
                }}
              >
                <FaPlay style={{ marginRight: '5px' }} /> Ejecutar Programa
              </button>
            </div>
          </div>

          {telemetry?.active_robot && activeScenarioObj?.robot_names?.length > 1 && (
            <div style={{ padding: '10px 20px', backgroundColor: '#161b22', borderBottom: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ color: '#c9d1d9', fontWeight: 'bold' }}>🤖 Controlando actualmente a:</span>
              <span style={{ color: '#58a6ff', fontWeight: 'bold', fontSize: '1.1rem' }}>{telemetry.active_robot}</span>
            </div>
          )}

          <div style={styles.blocklyWrapper}>
            <div style={{ height: '100%', display: editorMode === "blockly" ? 'block' : 'none' }}>
              <BlocklyEditor
                onCompile={handleCompile}
                activeScenarioObj={activeScenarioObj}
                executingBlockId={telemetry?.current_block || null}
                onSendToPython={sendBlocksToPython}
              />
            </div>
            <div style={{ height: '100%', display: editorMode === "python" ? 'block' : 'none' }}>
              <PythonEditor
                source={pythonSource}
                onSourceChange={setPythonSource}
                output={scriptOutput}
                running={scriptRunning}
              />
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
export default App;