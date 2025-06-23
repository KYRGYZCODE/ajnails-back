from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('leads', '0016_lead_reminder_minutes'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='is_additional',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='service',
            name='parent_service',
            field=models.ForeignKey(null=True, blank=True, to='leads.service', on_delete=models.SET_NULL, related_name='additional_services'),
        ),
        migrations.RemoveField(
            model_name='lead',
            name='service',
        ),
        migrations.AddField(
            model_name='lead',
            name='services',
            field=models.ManyToManyField(to='leads.service', related_name='leads', blank=True),
        ),
    ]
