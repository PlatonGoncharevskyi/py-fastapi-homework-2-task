import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status

from database import get_db, MovieModel
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas.movies import MovieDetailResponseSchema, MovieListResponseSchema, MovieCreateResponseSchem, \
    MovieCreateRequestSchema, MovieUpdateSchema, MovieSuccessResponse

router = APIRouter()

@router.get("/movies/", response_model=MovieListResponseSchema, name="get_movies")
async def get_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    total_items = await db.scalar(select(func.count()).select_from(MovieModel))
    total_items = int(total_items or 0)

    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_pages = math.ceil(total_items / per_page)

    if page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    offset = (page - 1) * per_page
    result = await db.scalars(
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)

    )
    movies = result.all()

    base_path = "/theater/movies/"

    def make_link(p: int) -> str:
        return f"{base_path}?page={p}&per_page={per_page}"

    prev_page = make_link(page - 1) if page > 1 else None
    next_page = make_link(page + 1) if page < total_pages else None

    return {
        "movies": movies,
        "prev_page": prev_page,
        "next_page": next_page,
        "total_pages": total_pages,
        "total_items": total_items,
    }


@router.get("/movies/{movie_id}/", response_model=MovieDetailResponseSchema)
async def get_film(movie_id : int, db: AsyncSession = Depends(get_db)):
    query = (
        select(MovieModel)
        .options(joinedload(MovieModel.country))
        .options(selectinload(MovieModel.genres))
        .options(selectinload(MovieModel.actors))
        .options(selectinload(MovieModel.languages))
        .where(MovieModel.id == movie_id)
    )

    result = await db.execute(query)
    film = result.scalar_one_or_none()
    if not film:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    return film


@router.post("/movies/", response_model=MovieCreateResponseSchem, status_code=status.HTTP_201_CREATED)
async def create_film(
    movie_request: MovieCreateRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    existing_movie = await db.scalar(
        select(MovieModel).where(
            MovieModel.name == movie_request.name,
            MovieModel.date == movie_request.date
        )
    )

    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_request.name}' and release date '{movie_request.date}' already exists."
        )

    new_movie = MovieModel(
        name=movie_request.name,
        date=movie_request.date,
        score=movie_request.score,
        overview=movie_request.overview,
        status=movie_request.status,
        budget=movie_request.budget,
        revenue=movie_request.revenue,
    )

    country = await db.scalar(
        select(CountryModel).where(CountryModel.code == movie_request.country)
    )
    if not country:
        country = CountryModel(code=movie_request.country, name=None)
        db.add(country)
        await db.flush()

    new_movie.country = country

    async def get_or_create_items(model_class, item_names: list[str]):
        if not item_names:
            return []

        existing_result = await db.scalars(
            select(model_class).where(model_class.name.in_(item_names))
        )
        existing_items = existing_result.all()
        existing_names = {item.name for item in existing_items}

        missing_names = set(item_names) - existing_names

        new_items = []
        for name in missing_names:
            item = model_class(name=name)
            db.add(item)
            new_items.append(item)

        return list(existing_items) + new_items

    new_movie.genres = await get_or_create_items(GenreModel, movie_request.genres)
    new_movie.actors = await get_or_create_items(ActorModel, movie_request.actors)
    new_movie.languages = await get_or_create_items(LanguageModel, movie_request.languages)

    try:
        db.add(new_movie)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid input data."
        )

    query = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages)
        )
        .where(MovieModel.id == new_movie.id)
    )

    result = await db.execute(query)
    final_movie = result.scalar_one()


    return final_movie


@router.delete("/movies/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_film(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MovieModel).where(MovieModel.id == movie_id)
    )

    movie = result.scalar_one_or_none()

    if movie is None:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    await db.delete(movie)
    await db.commit()

    return None

@router.patch("/movies/{movie_id}/", response_model=MovieSuccessResponse)
async def update_movie(
    movie_id: int,
    film_in: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db)
):
    query = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(query)
    movie = result.scalar_one_or_none()

    if movie is None:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    update_data = film_in.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(movie, key, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid input data."
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid input data."
        )

    return {"detail": "Movie updated successfully."}
