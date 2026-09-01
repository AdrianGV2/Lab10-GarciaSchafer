# Development helpers. See README.md for what each mode does.

.PHONY: install frontend serve validate clean

install:
	@echo "1. Python dependencies..."
	uv sync
	@echo "2. Node.js inside the virtualenv..."
	uv run nodeenv -p --quiet
	@echo "3. pnpm..."
	uv run npm install -g pnpm
	@echo "4. Front-end dependencies..."
	cd frontend && uv run pnpm install
	@echo "Ready. Run 'make serve' to start."

# Build the front end so the API can serve it on its own port.
frontend:
	cd frontend && uv run pnpm run build

serve:
	uv run simctl serve

validate:
	uv run simctl validate

clean:
	rm -rf frontend/dist runs
