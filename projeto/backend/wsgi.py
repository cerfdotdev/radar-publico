"""Ponto de entrada WSGI para o Gunicorn (gunicorn -c gunicorn.conf.py wsgi:app)."""

from app import create_app

app = create_app()
