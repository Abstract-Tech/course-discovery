# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-07-15 18:56
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0077_external-key'),
    ]

    operations = [
        migrations.DeleteModel(
            name='DrupalLoaderConfig',
        ),
    ]