from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DatasetVersion
from app.schemas import DatasetSplitSummary, DatasetVersionSummary, SampleDetail, SampleListItem
from app.services import catalog as catalog_service


router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/datasets", response_model=list[DatasetVersionSummary])
def list_datasets(db: Session = Depends(get_db)) -> list[DatasetVersionSummary]:
    catalog_service.sync_dataset_versions(db)
    return [
        DatasetVersionSummary(
            slug=item.slug,
            display_name=item.display_name,
            sample_count=item.sample_count,
            train_count=item.train_count,
            validation_count=item.validation_count,
            test_count=item.test_count,
            is_default=item.is_default,
            dataset_dir=item.dataset_dir,
            split_dir=item.split_dir,
        )
        for item in db.scalars(select(DatasetVersion).order_by(DatasetVersion.slug.asc())).all()
    ]


@router.get("/datasets/{slug}/splits", response_model=list[DatasetSplitSummary])
def list_dataset_splits(slug: str, db: Session = Depends(get_db)) -> list[DatasetSplitSummary]:
    try:
        dataset = catalog_service.get_dataset_version_or_404(db, slug)
        rows = catalog_service.list_split_summary(dataset)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [DatasetSplitSummary(**row) for row in rows]


@router.get("/datasets/{slug}/samples", response_model=list[SampleListItem])
def list_samples(
    slug: str,
    split: str = Query(...),
    search: str = Query(""),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[SampleListItem]:
    try:
        dataset = catalog_service.get_dataset_version_or_404(db, slug)
        rows = catalog_service.list_samples(dataset, split, search=search, offset=offset, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [SampleListItem(**row) for row in rows]


@router.get("/datasets/{slug}/samples/{sample_id}", response_model=SampleDetail)
def get_sample_detail(slug: str, sample_id: str, split: str = Query(...), db: Session = Depends(get_db)) -> SampleDetail:
    try:
        dataset = catalog_service.get_dataset_version_or_404(db, slug)
        row = catalog_service.get_sample_detail(dataset, split, sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SampleDetail(**row)
