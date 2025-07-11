from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_alter_employeeschedule_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='telegram_chat_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Telegram chat ID'),
        ),
    ]
