#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
  GESTION D'HOTEL - Logiciel de gestion complet
  ==============================================

  Lancement :
      python main.py

  La base de donnees "hotel.db" est creee automatiquement au meme endroit
  que ce fichier lors du premier lancement.
"""

import sys
import tkinter as tk
from tkinter import messagebox

from db.connection import init_db
from views.app import HotelApp


def main():
    try:
        init_db()
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Erreur de d\u00e9marrage",
            f"Impossible d'initialiser la base de donn\u00e9es :\n{exc}")
        root.destroy()
        sys.exit(1)

    app = HotelApp()
    app.mainloop()


if __name__ == "__main__":
    main()
