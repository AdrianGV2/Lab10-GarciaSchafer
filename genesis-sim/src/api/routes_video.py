"""MJPEG video stream of the simulator's headless camera."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/v1", tags=["video_stream"])

BOUNDARY = "frame"


class VideoStream:
    """Holds the most recent rendered frame for anyone watching the stream.

    A single latest-value slot rather than a queue: a client that falls behind
    should see the newest frame, never a backlog of stale ones.
    """

    def __init__(self, fps: float = 60.0):
        self._frame = None
        self._interval = 1.0 / fps

    def publish(self, jpeg_bytes: bytes) -> None:
        self._frame = jpeg_bytes

    async def frames(self):
        while True:
            if self._frame is not None:
                yield (
                    b"--" + BOUNDARY.encode() + b"\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + self._frame + b"\r\n"
                )
            await asyncio.sleep(self._interval)


@router.get("/video_feed")
def video_feed(request: Request):
    """The endpoint the React <img> tag connects to."""
    return StreamingResponse(
        request.app.state.video.frames(),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
    )
