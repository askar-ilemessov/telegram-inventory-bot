from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_warehouse_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchasetransaction',
            name='supplier',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Поставщик'),
        ),
    ]
