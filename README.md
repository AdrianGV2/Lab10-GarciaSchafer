generar la imagen en ventana nativa de genesis
.venv\Scripts\simctl.exe viewer configs\scenarios\lab10_scene_1.yml --api --backend cpu

escenario
uv run python agente.py dominio.pddl problems\problem_1.pddl lab10_scene_1