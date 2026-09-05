import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.budget import MonthlyBudget, BudgetAllocation, AllocationType
from app.schemas.budget import BudgetCreate, BudgetUpdate, BudgetResponse

router = APIRouter()


def _get_budget(db: Session, year: int, month: int) -> MonthlyBudget:
    budget = db.query(MonthlyBudget).filter(MonthlyBudget.year == year, MonthlyBudget.month == month).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


def _replace_allocations(budget: MonthlyBudget, allocations) -> None:
    budget.allocations.clear()
    for item in allocations:
        try:
            allocation_type = AllocationType(item.allocation_type)
        except ValueError:
            raise HTTPException(status_code=422, detail="allocation_type must be CONSUMPTION or INVESTMENT")
        budget.allocations.append(BudgetAllocation(
            category=item.category,
            planned_amount=item.planned_amount,
            allocation_type=allocation_type,
        ))


@router.get("/{year}/{month}", response_model=BudgetResponse)
def get_budget(year: int, month: int, db: Session = Depends(get_db)):
    return _get_budget(db, year, month)


@router.post("", response_model=BudgetResponse, status_code=201)
def create_budget(data: BudgetCreate, db: Session = Depends(get_db)):
    if db.query(MonthlyBudget).filter(MonthlyBudget.year == data.year, MonthlyBudget.month == data.month).first():
        raise HTTPException(status_code=409, detail="A budget already exists for this month")
    budget = MonthlyBudget(year=data.year, month=data.month, expected_income=data.expected_income, planned_saving=data.planned_saving, notes=data.notes)
    _replace_allocations(budget, data.allocations)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(budget_id: uuid.UUID, data: BudgetUpdate, db: Session = Depends(get_db)):
    budget = db.query(MonthlyBudget).filter(MonthlyBudget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    for field in ("expected_income", "planned_saving", "notes"):
        value = getattr(data, field)
        if value is not None:
            setattr(budget, field, value)
    if data.allocations is not None:
        _replace_allocations(budget, data.allocations)
    db.commit()
    db.refresh(budget)
    return budget