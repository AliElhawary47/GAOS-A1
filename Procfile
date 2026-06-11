web: gunicorn gaos_server:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
worker: python gaos_launcher.py full_team
