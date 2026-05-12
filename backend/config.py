"""Shared backend paths and runtime limits."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'ilm1300.db')
SCHEMA = os.path.join(BASE_DIR, 'schema.sql')
UPLOAD_DIR = os.path.join(BASE_DIR, 'data', 'uploads')
PART_IMAGES_DIR = os.path.join(BASE_DIR, 'data', 'part_images')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'tif', 'tiff'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024
