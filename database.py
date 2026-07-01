# ==============================================================================
# Module : database.py
# ==============================================================================

# Emplacement de la base de données (dans le même dossier que l'application)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "hotel.db")

# États possibles d'une chambre
ETATS_CHAMBRE = ["Libre", "Occupée", "Réservée", "Maintenance"]

# Catégories de dépenses
CATEGORIES_DEPENSE = [
    "Maintenance",
    "Ménage",
    "STEG (Électricité)",
    "SONEDE (Eau)",
    "Internet / Télécom",
    "Fournitures",
    "Salaires",
    "Impôts / Taxes",
    "Autre",
]

# Types d'identifiants pour les clients
TYPES_IDENTIFIANT = ["CIN", "Passeport", "Carte de séjour"]


def get_connection():
    """Retourne une connexion SQLite avec les clés étrangères activées."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée les tables si elles n'existent pas et insère des données de
    base (paramètres + quelques chambres) lors du premier lancement."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chambres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL DEFAULT 'Simple',
            prix REAL NOT NULL DEFAULT 0,
            etat TEXT NOT NULL DEFAULT 'Libre',
            description TEXT DEFAULT ''
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            type_identifiant TEXT NOT NULL DEFAULT 'CIN',
            numero_identifiant TEXT NOT NULL,
            date_naissance TEXT DEFAULT '',
            lieu_naissance TEXT DEFAULT '',
            adresse TEXT DEFAULT '',
            telephone TEXT DEFAULT '',
            venant_de TEXT DEFAULT '',
            allant_a TEXT DEFAULT '',
            chambre_id INTEGER,
            date_entree TEXT DEFAULT '',
            date_sortie TEXT DEFAULT '',
            statut TEXT NOT NULL DEFAULT 'En cours',
            FOREIGN KEY (chambre_id) REFERENCES chambres(id) ON DELETE SET NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS factures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            client_id INTEGER,
            nom_client TEXT DEFAULT '',
            date_facture TEXT NOT NULL,
            date_entree TEXT DEFAULT '',
            date_sortie TEXT DEFAULT '',
            nb_nuits INTEGER DEFAULT 0,
            montant_total REAL NOT NULL DEFAULT 0,
            remise REAL NOT NULL DEFAULT 0,
            mode_paiement TEXT DEFAULT 'Espèces',
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
        )
        """
    )
    # Ajouter la colonne si elle n'existe pas (base existante)
    try:
        cur.execute("ALTER TABLE factures ADD COLUMN nom_client TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE factures ADD COLUMN payee INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE clients ADD COLUMN solde REAL DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE factures ADD COLUMN montant_paye REAL DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS facture_lignes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facture_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            quantite REAL NOT NULL DEFAULT 1,
            prix_unitaire REAL NOT NULL DEFAULT 0,
            montant REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (facture_id) REFERENCES factures(id) ON DELETE CASCADE
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS depenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            categorie TEXT NOT NULL,
            description TEXT DEFAULT '',
            montant REAL NOT NULL DEFAULT 0,
            mode_paiement TEXT DEFAULT 'Espèces'
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            telephone TEXT DEFAULT '',
            type_identifiant TEXT DEFAULT 'CIN',
            numero_identifiant TEXT DEFAULT '',
            chambre_id INTEGER,
            date_arrivee TEXT NOT NULL,
            date_depart TEXT NOT NULL,
            nb_personnes INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            statut TEXT NOT NULL DEFAULT 'RESERVE',
            FOREIGN KEY (chambre_id) REFERENCES chambres(id) ON DELETE SET NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS parametres (
            cle TEXT PRIMARY KEY,
            valeur TEXT
        )
        """
    )

    conn.commit()

    # Paramètres par défaut (informations de l'hôtel utilisées sur les factures)
    defaults = {
        "nom_hotel": "Hôtel ",
        "adresse_hotel": "Adresse de l'hôtel, Tunisie",
        "telephone_hotel": "+216 00 000 000",
        "matricule_fiscal": "0000000A/A/M/000",
        "prochain_numero_facture": "1",
    }
    for cle, valeur in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO parametres (cle, valeur) VALUES (?, ?)",
            (cle, valeur),
        )
    conn.commit()

    # Si aucune chambre n'existe, on crée un parc de chambres par défaut
    # Si aucune chambre n'existe, on crée un parc de chambres par défaut
    # 4 étages x 4 chambres = 16 chambres, numérotées "étage-chambre" (ex: 1-3)
    cur.execute("SELECT COUNT(*) AS n FROM chambres")
    if cur.fetchone()["n"] == 0:
        chambres_defaut = []
        for etage in range(1, 5):
            for i in range(1, 5):
                numero = f"{etage}-{i}"
                if i == 1:
                    type_ch, prix = "Suite", 180.0
                elif i == 2:
                    type_ch, prix = "Double", 120.0
                else:
                    type_ch, prix = "Simple", 80.0
                chambres_defaut.append((numero, type_ch, prix, "Libre", ""))
        cur.executemany(
            "INSERT INTO chambres (numero, type, prix, etat, description) "
            "VALUES (?, ?, ?, ?, ?)",
            chambres_defaut,
        )
        conn.commit()

    conn.close()


# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------
def get_parametre(cle, defaut=""):
    conn = get_connection()
    row = conn.execute(
        "SELECT valeur FROM parametres WHERE cle = ?", (cle,)
    ).fetchone()
    conn.close()
    return row["valeur"] if row else defaut


def set_parametre(cle, valeur):
    conn = get_connection()
    conn.execute(
        "INSERT INTO parametres (cle, valeur) VALUES (?, ?) "
        "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
        (cle, str(valeur)),
    )
    conn.commit()
    conn.close()

