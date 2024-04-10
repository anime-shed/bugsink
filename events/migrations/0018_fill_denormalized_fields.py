# Generated by Django 4.2.11 on 2024-04-09 19:54

import json
from django.db import migrations
from issues.utils import get_denormalized_fields_for_data


def fill_denormalized_fields(apps, schema_editor):
    # This function does both events and issues; we don't care about the fact that this is "formally incorrect" as long
    # as we can keep developing for now.

    Event = apps.get_model('events', 'Event')

    for event in Event.objects.all():
        denormalized_fields = get_denormalized_fields_for_data(json.loads(event.data))
        for k, v in denormalized_fields.items():
            setattr(event, k, v)
        event.save()

        # inefficient, because we do each issue multiple times, but who cares, this is just to have something "for now"
        issue = event.issue
        for k, v in denormalized_fields.items():
            setattr(issue, k, v)
        issue.save()


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0017_event_last_frame_filename_event_last_frame_function_and_more'),
        ('ingest', '0003_decompressedevent_debug_info'),
        ('issues', '0021_issue_last_frame_filename_issue_last_frame_function_and_more'),
        ('projects', '0008_set_project_slugs'),
        ('releases', '0003_alter_release_version'),
    ]

    operations = [
        migrations.RunPython(fill_denormalized_fields),
    ]
