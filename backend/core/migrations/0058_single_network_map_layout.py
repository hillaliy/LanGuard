from django.db import migrations


def consolidate_layout(apps, schema_editor):
    Layout = apps.get_model('core', 'NetworkMapLayout')
    for layout in Layout.objects.all():
        # Keep an explicitly arranged infrastructure layout; otherwise repack on render.
        layout.positions = layout.infrastructure_positions or {}
        layout.revision += 1
        layout.save(update_fields=['positions', 'revision'])


class Migration(migrations.Migration):
    dependencies = [('core', '0057_network_map_background_commands')]
    operations = [
        migrations.RunPython(consolidate_layout, migrations.RunPython.noop),
        migrations.RemoveField(model_name='networkmaplayout', name='infrastructure_positions'),
    ]
