import React, { useRef, useState, useMemo, useEffect } from 'react';
import { BlocklyWorkspace } from 'react-blockly';
import * as Blockly from 'blockly/core';
import 'blockly/blocks';

Blockly.Blocks['manito_move'] = {
  init: function () {
    this.appendDummyInput()
      .appendField("Mover a X:")
      .appendField(new Blockly.FieldNumber(0, -200, 200, 1), "X")
      .appendField("Y:")
      .appendField(new Blockly.FieldNumber(0, -200, 200, 1), "Y")
      .appendField("Z:")
      .appendField(new Blockly.FieldNumber(0, 0, 200, 1), "Z");
    this.setInputsInline(true);
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Mueve el robot a las coordenadas (x,y,z) relativas a su base.");

    // Validación 
    this.setOnChange(function (changeEvent) {
      if (!this.workspace || this.isInFlyout) return;
      const x = this.getFieldValue('X');
      const y = this.getFieldValue('Y');
      const maxReach = 36;
      const distance = Math.sqrt(x * x + y * y);

      if (distance > maxReach) {
        this.setWarningText(`Fuera de alcance: La distancia horizontal requerida (${distance.toFixed(1)} cm) supera el límite físico del brazo (${maxReach} cm).`);
      } else {
        this.setWarningText(null);
      }
    });
  }
};

Blockly.Blocks['manito_move_joints'] = {
  init: function () {
    this.appendDummyInput()
      .appendField("Mover motores J1°:") //hombro
      .appendField(new Blockly.FieldNumber(0, -180, 180, 1), "J1")
      .appendField("J3°:") //codo
      .appendField(new Blockly.FieldNumber(0, -180, 180, 1), "J3")
      .appendField("J4°:") //muñeca
      .appendField(new Blockly.FieldNumber(0, -180, 180, 1), "J4")
      .appendField("Z cm:") //altura
      .appendField(new Blockly.FieldNumber(0, -10, 10, 1), "Z");
    this.setInputsInline(true);
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Mueve el robot definiendo los ángulos exactos de cada motor. Útil para posiciones precisas.");
  }
};

Blockly.Blocks['manito_cierra'] = {
  init: function () {
    this.appendDummyInput()
      .appendField("Cerrar Pinza");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(0);
    this.setTooltip("Cierra la pinza principal del robot actual.");
  }
};

Blockly.Blocks['manito_abre'] = {
  init: function () {
    this.appendDummyInput()
      .appendField("Abrir Pinza");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(120);
    this.setTooltip("Abre la pinza principal del robot actual.");
  }
};

Blockly.Blocks['manito_home'] = {
  init: function () {
    this.appendDummyInput()
      .appendField("Ir a Posición Home");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(290);
    this.setTooltip("Devuelve el robot a su posición segura.");
  }
};

Blockly.Blocks['manito_repeat'] = {
  init: function () {
    this.appendDummyInput()
      .appendField("Repetir")
      .appendField(new Blockly.FieldNumber(2, 1, 1000, 1), "TIMES")
      .appendField("veces");
    this.appendStatementInput("DO")
      .setCheck(null);
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(120);
    this.setTooltip("Repite los bloques en su interior el número de veces especificado.");
  }
};


import { pythonGenerator } from 'blockly/python';

// Los bloques generan llamadas a ManitoArm, la misma clase que usa el firmware,
// para que el código exportado corra tal cual en la pestaña Python.
pythonGenerator.forBlock['manito_move'] =
  function (block) {
    const x = block.getFieldValue('X');
    const y = block.getFieldValue('Y');
    const z = block.getFieldValue('Z');
    return `# "Mover a X:${x} Y:${y} Z:${z}" no tiene equivalente en la API Python; usa move_joints.\n`;
  };

pythonGenerator.forBlock['manito_move_joints'] =
  function (block) {
    const j1 = block.getFieldValue('J1');
    const j3 = block.getFieldValue('J3');
    const j4 = block.getFieldValue('J4');
    const z = block.getFieldValue('Z');

    return `brazo.move_joints(${j1}, ${j3}, ${j4}, ${z})\n`;
  };

pythonGenerator.forBlock['manito_cierra'] =
  function (block) {
    return `brazo.gripper(True)\n`;
  };
pythonGenerator.forBlock['manito_abre'] =
  function (block) {
    return `brazo.gripper(False)\n`;
  };
pythonGenerator.forBlock['manito_home'] =
  function (block) {
    return `brazo.home()\n`;
  };
pythonGenerator.forBlock['manito_switch'] =
  function (block) {
    const name = block.getFieldValue('ROBOT_NAME');
    return `# "Cambiar control a: ${name}" no tiene equivalente en la API Python.\n`;
  };
pythonGenerator.forBlock['manito_repeat'] =
  function (block) {
    const times = block.getFieldValue('TIMES');
    const body = pythonGenerator.statementToCode(block, 'DO') || '  pass\n';
    return `for _ in range(${times}):\n${body}\n`;
  };

const PYTHON_HEADER = `from manito_api import ManitoArm\n\nbrazo = ManitoArm()\n\n`;

export const workspaceToPython = (workspace) => {
  if (!workspace) return PYTHON_HEADER;
  return PYTHON_HEADER + pythonGenerator.workspaceToCode(workspace);
};

const exportToPython = (workspace) => {
  const fullCode = workspaceToPython(workspace);

  const blob = new Blob([fullCode], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'manito_program.py';
  a.click();
  URL.revokeObjectURL(url);
};

const toolbox = {
  kind: "categoryToolbox",
  contents: [
    {
      kind: "category",
      name: "Movimiento",
      colour: "160",
      contents: [
        { kind: "block", type: "manito_move" },
        { kind: "block", type: "manito_move_joints" }
      ]
    },
    {
      kind: "category",
      name: "Control",
      colour: "120",
      contents: [
        { kind: "block", type: "manito_repeat" }
      ]
    },
    {
      kind: "category",
      name: "Inicio",
      colour: "230",
      contents: [
        { kind: "block", type: "manito_home" }
      ]
    },
    {
      kind: "category",
      name: "Garra",
      colour: "0",
      contents: [
        { kind: "block", type: "manito_cierra" },
        { kind: "block", type: "manito_abre" }
      ]
    }
  ]
};

// Componente Principal
const BlocklyEditor = ({ onCompile, activeScenarioObj, executingBlockId, onSendToPython }) => {
  const [workspaceXml, setWorkspaceXml] = useState("");
  const workspaceRef = useRef(null);

  // Efecto para resaltar el bloque en ejecución
  useEffect(() => {
    console.log("Intentando resaltar bloque ID:", executingBlockId);
    if (workspaceRef.current && typeof workspaceRef.current.highlightBlock === 'function') {
      try {
        if (executingBlockId) {
          workspaceRef.current.highlightBlock(executingBlockId);
        } else {
          workspaceRef.current.highlightBlock(null);
        }
      } catch (err) {
        console.warn("No se pudo resaltar el bloque de Blockly:", err);
      }
    } else {
      console.log("El workspace no está listo o highlightBlock no es una función");
    }
  }, [executingBlockId]);

  const dynamicToolbox = useMemo(() => {
    const hasMultipleRobots = activeScenarioObj?.robot_names?.length > 1;

    if (hasMultipleRobots) {
      const robotOptions = activeScenarioObj.robot_names.map(name => [name, name]);

      Blockly.Blocks['manito_switch'] = {
        init: function () {
          this.appendDummyInput()
            .appendField("Cambiar control a:")
            .appendField(new Blockly.FieldDropdown(robotOptions), "ROBOT_NAME");
          this.setPreviousStatement(true, null);
          this.setNextStatement(true, null);
          this.setColour(330);
          this.setTooltip("Cambia el foco de control al robot seleccionado.");
        }
      };

      const modifiedToolbox = JSON.parse(JSON.stringify(toolbox));
      modifiedToolbox.contents.unshift({
        kind: "category",
        name: "Sistema",
        colour: "330",
        contents: [
          { kind: "block", type: "manito_switch" }
        ]
      });
      return modifiedToolbox;
    }

    return toolbox;
  }, [activeScenarioObj]);

  const workspaceDidChange = (workspace) => {
    const extractCommands = () => {
      const topBlocks = workspace.getTopBlocks(true);
      if (topBlocks.length === 0) return [];

      const commands = [];

      const processBlock = (block) => {
        let currentBlock = block;
        while (currentBlock) {
          if (currentBlock.type === 'manito_move') {
            commands.push({
              action: "move_to",
              block_id: currentBlock.id,
              x: currentBlock.getFieldValue('X') / 100.0,
              y: currentBlock.getFieldValue('Y') / 100.0,
              z: currentBlock.getFieldValue('Z') / 100.0
            });
          } else if (currentBlock.type === 'manito_move_joints') {
            commands.push({
              action: "move_joints",
              block_id: currentBlock.id,
              metadata: {
                j1: currentBlock.getFieldValue('J1'),
                z: currentBlock.getFieldValue('Z'),
                j3: currentBlock.getFieldValue('J3'),
                j4: currentBlock.getFieldValue('J4'),
              }
            });
          } else if (currentBlock.type === 'manito_cierra') {
            commands.push({ action: "cierra", block_id: currentBlock.id });
          } else if (currentBlock.type === 'manito_abre') {
            commands.push({ action: "abre", block_id: currentBlock.id });
          } else if (currentBlock.type === 'manito_home') {
            commands.push({ action: "home", block_id: currentBlock.id });
          } else if (currentBlock.type === 'manito_switch') {
            commands.push({ action: "switch_robot", block_id: currentBlock.id, robot_name: currentBlock.getFieldValue('ROBOT_NAME') });
          } else if (currentBlock.type === 'manito_repeat') {
            const times = currentBlock.getFieldValue('TIMES') || 1;
            const nestedBlock = currentBlock.getInputTargetBlock('DO');
            if (nestedBlock) {
              for (let i = 0; i < times; i++) {
                processBlock(nestedBlock);
              }
            }
          } else if (currentBlock.customAction) {
            commands.push({ action: currentBlock.customAction, block_id: currentBlock.id, ...currentBlock.customParams });
          }
          currentBlock = currentBlock.getNextBlock();
        }
      };

      processBlock(topBlocks[0]);
      return commands;
    };

    const cmds = extractCommands();
    if (onCompile) {
      onCompile(cmds);
    }
  };

  return (
    <div style={{ height: '100%', width: '100%', border: '1px solid #444', borderRadius: '8px', overflow: 'hidden', position: 'relative' }}>
      <style>{`
        .blockly-workspace { position: absolute; top: 0; left: 0; height: 100%; width: 100%; }
        .blocklyTreeLabel { color: #ffffff !important; font-weight: 500; font-family: 'Inter', sans-serif; }
      `}</style>
      <BlocklyWorkspace
        className="blockly-workspace"
        toolboxConfiguration={dynamicToolbox}
        initialXml={workspaceXml}
        onWorkspaceChange={workspaceDidChange}
        onInject={(workspace) => { workspaceRef.current = workspace; }}
        workspaceConfiguration={{
          grid: {
            spacing: 20,
            length: 3,
            colour: '#ccc',
            snap: true
          },
          trashcan: true,
          theme: Blockly.Themes.Dark
        }}
      />
      <div style={{ position: 'absolute', bottom: '15px', right: '10px', display: 'flex', gap: '8px' }}>
        {onSendToPython && (
          <button
            onClick={() => onSendToPython(workspaceToPython(workspaceRef.current))}
            style={{ padding: '8px 16px' }}
            title="Convierte estos bloques en código Python editable"
          >
            Abrir en Python
          </button>
        )}
        <button onClick={() => exportToPython(workspaceRef.current)} style={{ padding: '8px 16px' }}>
          Exportar a Python
        </button>
      </div>
    </div>
  );
};

export default BlocklyEditor;
