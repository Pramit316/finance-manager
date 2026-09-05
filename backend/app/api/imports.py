"""Statement import API endpoints."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account
from app.models.statement_import import StatementImport, StatementSource
from app.schemas.import_schema import ImportResultResponse
from app.services.import_service import import_statement

from typing import Optional
from app.models.account import Account, AccountType
from app.parsers.nabil import NabilStatementParser
from app.parsers.esewa import EsewaStatementParser
from app.parsers.standard_chartered import StandardCharteredStatementParser

router = APIRouter()

# Maximum upload size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload", response_model=ImportResultResponse)
async def upload_statement(
    source: str = Form(...),
    file: UploadFile = File(...),
    account_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload and import a financial statement."""
    # Validate source
    try:
        source_enum = StatementSource(source.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source: {source}. Must be ESEWA, NABIL, or STANDARD_CHARTERED.",
        )

    # Read file
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    # Resolve or infer account
    acc_uuid = None
    if account_id and account_id.strip() and account_id != "infer" and account_id != "undefined" and account_id != "null":
        try:
            acc_uuid = uuid.UUID(account_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid account ID UUID format")
        
        account = db.query(Account).filter(Account.id == acc_uuid).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
    else:
        # Infer from statement metadata
        if source_enum == StatementSource.NABIL:
            parser = NabilStatementParser()
        elif source_enum == StatementSource.STANDARD_CHARTERED:
            parser = StandardCharteredStatementParser()
        else:
            parser = EsewaStatementParser()
            
        try:
            parsed_stmt = parser.parse(file_bytes, file.filename or "unknown")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse statement for account inference: {str(e)}")
            
        # Determine account number to look up/create
        if source_enum == StatementSource.ESEWA:
            # For eSewa, assume all statements belong to the same default wallet
            target_account_number = "ESEWA_DEFAULT"
            account_name = "eSewa Wallet"
        else:
            if not parsed_stmt.account_number:
                raise HTTPException(
                    status_code=400, 
                    detail="Could not infer account number from Nabil statement. Please specify an Account ID manually."
                )
            target_account_number = parsed_stmt.account_number
            institution_name = "Standard Chartered" if source_enum == StatementSource.STANDARD_CHARTERED else "Nabil"
            account_name = f"{institution_name} ({target_account_number})"
            
        # Try to find existing account by account number and institution
        account = db.query(Account).filter(
            Account.account_number == target_account_number,
            Account.institution == source_enum.value
        ).first()
        
        if not account:
            # Auto-create account
            acc_type = AccountType.BANK if source_enum in (StatementSource.NABIL, StatementSource.STANDARD_CHARTERED) else AccountType.WALLET
            account = Account(
                name=account_name,
                account_number=target_account_number,
                institution=source_enum.value,
                account_type=acc_type,
                currency=parsed_stmt.currency or "NPR",
                is_active=True
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            
        acc_uuid = account.id

    # Run import pipeline
    result = import_statement(
        db=db,
        account_id=acc_uuid,
        source=source_enum.value,
        filename=file.filename or "unknown",
        file_bytes=file_bytes,
    )

    return ImportResultResponse(
        import_id=result.id,
        source=result.source.value,
        status=result.status.value,
        filename=result.filename,
        period_from=result.period_from,
        period_to=result.period_to,
        opening_balance=result.opening_balance,
        closing_balance=result.closing_balance,
        currency=result.currency,
        rows_read=result.rows_read,
        rows_parsed=result.rows_parsed,
        rows_inserted=result.rows_inserted,
        duplicate_rows=result.duplicate_rows,
        invalid_rows=result.invalid_rows,
        total_debit=result.total_debit,
        total_credit=result.total_credit,
        reconciliation_status=result.reconciliation_status.value,
        reconciliation_difference=result.reconciliation_difference,
        error_message=result.error_message,
        created_at=result.created_at,
    )


@router.get("/", response_model=list[ImportResultResponse])
def list_imports(db: Session = Depends(get_db)):
    """List all statement imports, most recent first."""
    stmt_imports = (
        db.query(StatementImport)
        .order_by(StatementImport.created_at.desc())
        .all()
    )
    return [
        ImportResultResponse(
            import_id=si.id,
            source=si.source.value,
            status=si.status.value,
            filename=si.filename,
            period_from=si.period_from,
            period_to=si.period_to,
            opening_balance=si.opening_balance,
            closing_balance=si.closing_balance,
            currency=si.currency,
            rows_read=si.rows_read,
            rows_parsed=si.rows_parsed,
            rows_inserted=si.rows_inserted,
            duplicate_rows=si.duplicate_rows,
            invalid_rows=si.invalid_rows,
            total_debit=si.total_debit,
            total_credit=si.total_credit,
            reconciliation_status=si.reconciliation_status.value,
            reconciliation_difference=si.reconciliation_difference,
            error_message=si.error_message,
            created_at=si.created_at,
        )
        for si in stmt_imports
    ]


@router.get("/{import_id}", response_model=ImportResultResponse)
def get_import(import_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get import result by ID."""
    stmt_import = (
        db.query(StatementImport).filter(StatementImport.id == import_id).first()
    )
    if not stmt_import:
        raise HTTPException(status_code=404, detail="Import not found")

    return ImportResultResponse(
        import_id=stmt_import.id,
        source=stmt_import.source.value,
        status=stmt_import.status.value,
        filename=stmt_import.filename,
        period_from=stmt_import.period_from,
        period_to=stmt_import.period_to,
        opening_balance=stmt_import.opening_balance,
        closing_balance=stmt_import.closing_balance,
        currency=stmt_import.currency,
        rows_read=stmt_import.rows_read,
        rows_parsed=stmt_import.rows_parsed,
        rows_inserted=stmt_import.rows_inserted,
        duplicate_rows=stmt_import.duplicate_rows,
        invalid_rows=stmt_import.invalid_rows,
        total_debit=stmt_import.total_debit,
        total_credit=stmt_import.total_credit,
        reconciliation_status=stmt_import.reconciliation_status.value,
        reconciliation_difference=stmt_import.reconciliation_difference,
        error_message=stmt_import.error_message,
        created_at=stmt_import.created_at,
    )
