# ---------------------------------------------------------------------------
# Chambres
# ---------------------------------------------------------------------------
def get_chambres():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM chambres ORDER BY numero").fetchall()
    conn.close()
    return rows


def get_chambre(chambre_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM chambres WHERE id = ?", (chambre_id,)
    ).fetchone()
    conn.close()
    return row


def get_chambres_libres():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM chambres WHERE etat = 'Libre' ORDER BY numero"
    ).fetchall()
    conn.close()
    return rows


def add_chambre(numero, type_ch, prix, etat="Libre", description=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO chambres (numero, type, prix, etat, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (numero, type_ch, prix, etat, description),
    )
    conn.commit()
    conn.close()


def update_chambre(chambre_id, numero, type_ch, prix, etat, description):
    conn = get_connection()
    conn.execute(
        "UPDATE chambres SET numero=?, type=?, prix=?, etat=?, description=? "
        "WHERE id=?",
        (numero, type_ch, prix, etat, description, chambre_id),
    )
    conn.commit()
    conn.close()


def set_chambre_etat(chambre_id, etat):
    conn = get_connection()
    conn.execute("UPDATE chambres SET etat=? WHERE id=?", (etat, chambre_id))
    conn.commit()
    conn.close()


def delete_chambre(chambre_id):
    conn = get_connection()
    conn.execute("DELETE FROM chambres WHERE id=?", (chambre_id,))
    conn.commit()
    conn.close()