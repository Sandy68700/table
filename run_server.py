import os
from waitress import serve
from tracking_server import app

if __name__ == "__main__":
    # Render fournit le port via la variable d'environnement PORT
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Serveur Waitress démarré sur http://0.0.0.0:{port}")
    serve(app, host="0.0.0.0", port=port)
