from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0019_lead_payment_url'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='service',
            name='parent_service',
        ),
        migrations.AddField(
            model_name='service',
            name='parent_services',
            field=models.ManyToManyField(
                to='leads.service',
                symmetrical=False,
                related_name='additional_services',
                blank=True
            ),
        ),
    ]
