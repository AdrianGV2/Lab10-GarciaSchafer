FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# libegl1/libgl1 are what Genesis needs to render the streaming camera with no
# display attached; libglfw3 is only used by the native viewer.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libglfw3 \
    libegl1 \
    libgomp1 \
    make \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . /app

RUN make install && make frontend

# One port: the API serves the built front end from the same origin.
EXPOSE 8000

CMD ["uv", "run", "simctl", "serve", "--host", "0.0.0.0", "--port", "8000"]
