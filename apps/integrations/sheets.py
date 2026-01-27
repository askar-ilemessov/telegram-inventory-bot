"""
Google Sheets Integration Service.
Exports transactions to Google Sheets with batching to avoid API limits.
"""
import logging
from typing import List, Optional
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.db import transaction
import gspread
from google.oauth2.service_account import Credentials
from apps.pos.models import Transaction

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service for exporting data to Google Sheets."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self):
        """Initialize Google Sheets client."""
        self.enabled = settings.GOOGLE_SHEETS_ENABLED
        self.sheet_id = settings.GOOGLE_SHEET_ID
        self.service_account_file = settings.GOOGLE_SERVICE_ACCOUNT_FILE
        self.client: Optional[gspread.Client] = None
        
        if self.enabled:
            self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with Google Sheets API."""
        try:
            credentials = Credentials.from_service_account_file(
                self.service_account_file,
                scopes=self.SCOPES
            )
            self.client = gspread.authorize(credentials)
            logger.info("Successfully authenticated with Google Sheets API")
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Sheets: {e}")
            self.enabled = False
    
    def _get_worksheet(self, worksheet_name: str = "Transactions"):
        """
        Get or create worksheet.
        
        Args:
            worksheet_name: Name of the worksheet
            
        Returns:
            Worksheet instance
        """
        if not self.enabled or not self.client:
            raise ValueError("Google Sheets integration is not enabled")
        
        try:
            spreadsheet = self.client.open_by_key(self.sheet_id)
            
            # Try to get existing worksheet
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                # Create new worksheet with headers
                worksheet = spreadsheet.add_worksheet(
                    title=worksheet_name,
                    rows=1000,
                    cols=20
                )
                # Add headers
                headers = [
                    'ID', 'Дата', 'Смена ID', 'Сотрудник', 'Локация',
                    'Товар', 'Категория', 'Тип', 'Количество', 'Сумма',
                    'Способ оплаты', 'Примечания'
                ]
                worksheet.append_row(headers)
            
            return worksheet
        except Exception as e:
            logger.error(f"Failed to get worksheet: {e}")
            raise
    
    @transaction.atomic
    def export_transactions(self, batch_size: int = 100) -> int:
        """
        Export unexported transactions to Google Sheets in batches.
        
        Args:
            batch_size: Number of transactions to export in one batch
            
        Returns:
            Number of transactions exported
        """
        if not self.enabled:
            logger.warning("Google Sheets export is disabled")
            return 0
        
        # Get unexported transactions
        transactions = Transaction.objects.filter(
            exported_at__isnull=True
        ).select_related(
            'shift__staff__user',
            'shift__location',
            'product__category'
        ).prefetch_related(
            'payments'
        ).order_by('created_at')[:batch_size]
        
        if not transactions:
            logger.info("No transactions to export")
            return 0
        
        try:
            worksheet = self._get_worksheet()
            
            # Prepare rows for batch insert
            rows = []
            transaction_ids = []
            
            for trans in transactions:
                # Get payment method (first payment)
                payment_method = ''
                if trans.payments.exists():
                    payment_method = trans.payments.first().get_method_display()
                
                row = [
                    str(trans.id),
                    trans.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    str(trans.shift.id),
                    trans.shift.staff.full_name,
                    trans.shift.location.name,
                    trans.product.name,
                    trans.product.category.name,
                    trans.get_transaction_type_display(),
                    str(trans.qty),
                    str(trans.amount),
                    payment_method,
                    trans.notes
                ]
                rows.append(row)
                transaction_ids.append(trans.id)
            
            # Batch append to Google Sheets
            worksheet.append_rows(rows, value_input_option='USER_ENTERED')
            
            # Mark transactions as exported
            now = timezone.now()
            Transaction.objects.filter(id__in=transaction_ids).update(
                exported_at=now
            )
            
            logger.info(f"Successfully exported {len(rows)} transactions to Google Sheets")
            return len(rows)
            
        except Exception as e:
            logger.error(f"Failed to export transactions: {e}")
            raise
    
    def export_all_pending(self) -> int:
        """
        Export all pending transactions in batches.
        
        Returns:
            Total number of transactions exported
        """
        total_exported = 0
        batch_size = 100
        
        while True:
            exported = self.export_transactions(batch_size=batch_size)
            total_exported += exported
            
            if exported < batch_size:
                # No more transactions to export
                break
        
        return total_exported

