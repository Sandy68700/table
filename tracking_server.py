@app.route("/", methods=["GET", "POST"])
def home():
    message = ""
    file_exists = os.path.exists(CONTACTS_FILE)

    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]
            if file.filename != "":
                file.save(CONTACTS_FILE)
                message = "✅ Fichier contacts.xlsx enregistré avec succès !"
                file_exists = True
            else:
                message = "⚠ Aucun fichier sélectionné."
        else:
            message = "⚠ Clé 'file' manquante."

    html = f"""
    <h1>📊 Serveur de Tracking</h1>
    <p>{message}</p>

    <!-- Formulaire upload -->
    <form method="post" enctype="multipart/form-data">
        <label>Uploader votre fichier contacts.xlsx :</label>
        <input type="file" name="file" accept=".xlsx" required>
        <button type="submit">Uploader</button>
    </form>

    <br>

    <!-- Bouton téléchargement si fichier existant -->
    {'<a href="/download">⬇ Télécharger contacts.xlsx</a><br><br>' if file_exists else ''}

    <a href="/report">Voir le rapport des ouvertures</a><br>
    <a href="/opens">Voir JSON brut des ouvertures</a>
    """
    return render_template_string(html)

# --- Route pour télécharger contacts.xlsx ---
from flask import send_file

@app.route("/download")
def download_contacts():
    if os.path.exists(CONTACTS_FILE):
        return send_file(CONTACTS_FILE, as_attachment=True)
    else:
        return "⚠ Aucun fichier contacts.xlsx disponible pour le téléchargement.", 404
