from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_warehouse_models'),
        ('pos', '0002_shift_total_transfer'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShiftSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='Количество на витрине')),
                ('notes', models.TextField(blank=True, verbose_name='Примечания')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shift_snapshots', to='inventory.product', verbose_name='Товар')),
                ('shift', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_snapshots', to='pos.shift', verbose_name='Смена')),
            ],
            options={
                'verbose_name': 'Снимок остатков смены',
                'verbose_name_plural': 'Снимки остатков смен',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='shiftsnapshot',
            index=models.Index(fields=['shift', 'product'], name='pos_shiftsn_shift_i_a0b2e2_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='shiftsnapshot',
            unique_together={('shift', 'product')},
        ),
        migrations.AlterField(
            model_name='transaction',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Сумма'),
        ),
        migrations.AlterField(
            model_name='payment',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Сумма'),
        ),
    ]
