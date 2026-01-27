"""
Shift Logger - logs all bot interactions to files per shift.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from apps.pos.models import Shift


class ShiftLogger:
    """Logger for shift activities."""
    
    LOGS_DIR = Path("shift_logs")
    
    @classmethod
    def _ensure_logs_dir(cls):
        """Ensure logs directory exists."""
        cls.LOGS_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def _get_log_file_path(cls, shift: Shift) -> Path:
        """
        Get log file path for a shift.
        
        Args:
            shift: Shift instance
            
        Returns:
            Path to log file
        """
        cls._ensure_logs_dir()
        
        # Format: shift_LOCATION_YYYYMMDD_HHMMSS.log
        start_time = shift.started_at.strftime('%Y%m%d_%H%M%S')
        location_name = shift.location.name.replace(' ', '_')
        filename = f"shift_{location_name}_{start_time}.log"
        
        return cls.LOGS_DIR / filename
    
    @classmethod
    def log_shift_start(cls, shift: Shift):
        """Log shift start."""
        log_file = cls._get_log_file_path(shift)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write(f"СМЕНА ОТКРЫТА\n")
            f.write("=" * 60 + "\n")
            f.write(f"Дата и время: {shift.started_at.strftime('%d.%m.%Y %H:%M:%S')}\n")
            f.write(f"Сотрудник: {shift.staff.full_name}\n")
            f.write(f"Локация: {shift.location.name}\n")
            f.write(f"Telegram ID: {shift.staff.telegram_id}\n")
            f.write("=" * 60 + "\n\n")
    
    @classmethod
    def log_sale(cls, shift: Shift, product_name: str, qty: float, amount: float, payment_method: str):
        """Log a sale transaction."""
        log_file = cls._get_log_file_path(shift)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            f.write(f"[{timestamp}] 📦 ПРОДАЖА\n")
            f.write(f"  Товар: {product_name}\n")
            f.write(f"  Количество: {qty}\n")
            f.write(f"  Сумма: {amount}₸\n")
            f.write(f"  Оплата: {payment_method}\n")
            f.write("-" * 60 + "\n\n")
    
    @classmethod
    def log_refund(cls, shift: Shift, product_name: str, qty: float, amount: float, payment_method: str):
        """Log a refund transaction."""
        log_file = cls._get_log_file_path(shift)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            f.write(f"[{timestamp}] ↩️ ВОЗВРАТ\n")
            f.write(f"  Товар: {product_name}\n")
            f.write(f"  Количество: {qty}\n")
            f.write(f"  Сумма: {amount}₸\n")
            f.write(f"  Оплата: {payment_method}\n")
            f.write("-" * 60 + "\n\n")
    
    @classmethod
    def log_report_view(cls, shift: Shift, report_type: str):
        """Log report viewing."""
        log_file = cls._get_log_file_path(shift)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            f.write(f"[{timestamp}] 📊 ПРОСМОТР ОТЧЕТА: {report_type}\n")
            f.write("-" * 60 + "\n\n")
    
    @classmethod
    def log_shift_close(cls, shift: Shift, summary: dict):
        """Log shift closing with summary."""
        log_file = cls._get_log_file_path(shift)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"СМЕНА ЗАКРЫТА\n")
            f.write("=" * 60 + "\n")
            f.write(f"Дата и время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
            f.write(f"Продолжительность: {shift.closed_at - shift.started_at}\n\n")
            
            f.write("ИТОГОВАЯ СТАТИСТИКА:\n")
            f.write(f"  Продажи: {summary.get('sales_total', 0)}₸ ({summary.get('sales_count', 0)} транзакций)\n")
            f.write(f"  Возвраты: {summary.get('refunds_total', 0)}₸ ({summary.get('refunds_count', 0)} транзакций)\n")
            f.write(f"  Чистая прибыль: {summary.get('net_total', 0)}₸\n\n")
            
            f.write("РАЗБИВКА ПО МЕТОДАМ ОПЛАТЫ:\n")
            f.write(f"  💵 Наличные: {summary.get('total_cash', 0)}₸\n")
            f.write(f"  💳 Карта: {summary.get('total_card', 0)}₸\n")
            f.write(f"  📱 Перевод: {summary.get('total_transfer', 0)}₸\n")
            
            f.write("=" * 60 + "\n")
    
    @classmethod
    def log_action(cls, shift: Shift, action: str, details: Optional[str] = None):
        """Log a general action."""
        log_file = cls._get_log_file_path(shift)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            f.write(f"[{timestamp}] {action}\n")
            if details:
                f.write(f"  {details}\n")
            f.write("-" * 60 + "\n\n")

