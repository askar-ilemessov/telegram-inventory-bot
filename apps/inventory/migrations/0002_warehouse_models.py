from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='stock_quantity',
        ),
        migrations.CreateModel(
            name='StorageStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=8, verbose_name='Количество на складе')),
                ('last_purchase_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Последняя цена закупки')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='storage_stocks', to='core.location', verbose_name='Локация')),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='storage_stock', to='inventory.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Остаток на складе',
                'verbose_name_plural': 'Остатки на складе',
                'ordering': ['product__name'],
            },
        ),
        migrations.AddIndex(
            model_name='storagestock',
            index=models.Index(fields=['location', 'product'], name='inventory_s_locatio_83f0bb_idx'),
        ),
        migrations.CreateModel(
            name='DisplayStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=8, verbose_name='Количество на витрине')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='display_stocks', to='core.location', verbose_name='Локация')),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='display_stock', to='inventory.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Остаток на витрине',
                'verbose_name_plural': 'Остатки на витрине',
                'ordering': ['product__name'],
            },
        ),
        migrations.AddIndex(
            model_name='displaystock',
            index=models.Index(fields=['location', 'product'], name='inventory_d_locatio_b61b7b_idx'),
        ),
        migrations.CreateModel(
            name='PurchaseTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='Количество')),
                ('purchase_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Цена закупки за единицу')),
                ('total_cost', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Общая стоимость')),
                ('supplier', models.CharField(blank=True, max_length=255, verbose_name='Поставщик')),
                ('notes', models.TextField(blank=True, verbose_name='Примечания')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата закупки')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='purchases', to=settings.AUTH_USER_MODEL, verbose_name='Создал')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='purchases', to='core.location', verbose_name='Локация')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='purchases', to='inventory.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Закупка',
                'verbose_name_plural': 'Закупки',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='purchasetransaction',
            index=models.Index(fields=['location', 'created_at'], name='inventory_p_locatio_0c92e2_idx'),
        ),
        migrations.AddIndex(
            model_name='purchasetransaction',
            index=models.Index(fields=['product', 'created_at'], name='inventory_p_product_a5f588_idx'),
        ),
        migrations.CreateModel(
            name='TransferTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='Количество')),
                ('notes', models.TextField(blank=True, verbose_name='Примечания')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата перемещения')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfers', to=settings.AUTH_USER_MODEL, verbose_name='Создал')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfers', to='core.location', verbose_name='Локация')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfers', to='inventory.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Перемещение',
                'verbose_name_plural': 'Перемещения',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='transfertransaction',
            index=models.Index(fields=['location', 'created_at'], name='inventory_t_locatio_965782_idx'),
        ),
        migrations.AddIndex(
            model_name='transfertransaction',
            index=models.Index(fields=['product', 'created_at'], name='inventory_t_product_747617_idx'),
        ),
    ]
