from pydantic import BaseModel, Field


class Segment(BaseModel):
    id: int
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: str


class TranscriptResponse(BaseModel):
    language: str | None
    duration: float
    text: str
    segments: list[Segment]
