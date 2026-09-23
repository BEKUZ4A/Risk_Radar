from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('payments', '0003_alter_payment_employee')]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='refunded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
