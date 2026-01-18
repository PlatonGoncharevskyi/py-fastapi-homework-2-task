from datetime import date, timedelta
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

from database.models import MovieStatusEnum


class MovieBase(BaseModel):
    id: int
    name: str
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: str


class CountrySchema(BaseModel):
    id: int
    code: str
    name: str | None

    class Config:
        from_attributes = True


class GenreActorLanguageSchema(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class MovieCreateRequestSchema(BaseModel):
    name: str = Field(..., max_length=255)
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: str

    status: MovieStatusEnum

    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)

    country: str = Field(..., min_length=3, max_length=3)

    genres: List[str]
    actors: List[str]
    languages: List[str]

    @field_validator("date")
    def validate_date_future(cls, v: date):
        one_year_future = date.today() + timedelta(days=365)
        if v > one_year_future:
            raise ValueError("Date must not be more than one year in the future")
        return v


class MovieCreateResponseSchem(MovieBase):
    status: MovieStatusEnum
    budget: float
    revenue: float
    country: CountrySchema

    genres: list[GenreActorLanguageSchema]
    actors: list[GenreActorLanguageSchema]
    languages: list[GenreActorLanguageSchema]

    class Config:
        from_attributes = True


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    overview: Optional[str] = None
    status: Optional[MovieStatusEnum] = None
    budget: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)

    class Config:
        from_attributes = True

class MovieSuccessResponse(BaseModel):
    detail: str


class MovieDetailResponseSchema(MovieCreateResponseSchem):
    pass

    class Config:
        from_attributes = True



class MovieListResponseSchema(BaseModel):
    movies: List[MovieBase]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int