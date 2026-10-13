import sqlite3
def init_db():
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()

    # Table des équipements
    

   
    c.execute('''
        CREATE TABLE  IF NOT EXISTS equipements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Nom TEXT NOT NULL,
            Numero_salle TEXT,
            Nom_salle TEXT,
            Responsable TEXT,
            Coresponsable TEXT,
            Categorie TEXT,  
            Quota_fct_avant_maintenance INTEGER,
            Quota_fct_par_mois INTEGER,  
            Date_maintenance TEXT,
            Date_installation TEXT,
            Nombre_heures_fct_depuis_maintenance INTEGER,
            Nombre_heure_fct_depuis_installation INTEGER,
            Etat TEXT,
            Besoin_maintenance TEXT,
            Date_prochain_arret TEXT,
            Compteur_d_arret_en_jours INTEGER, 
            Protocole TEXT,
            Demande_permission TEXT,
            Nb_jours_max_reservation INTEGER



        )
    ''')
    # Migration : ajoute la colonne 'Nb_jours_max_reservation' si la table
    # 'equipements' existait deja sans cette colonne.
    # Nombre de jours consecutifs maximum autorise pour une reservation de cet
    # equipement (defini par l'admin). NULL ou 0 = pas de limite.
    c.execute("PRAGMA table_info(equipements)")
    equip_cols = [row[1] for row in c.fetchall()]
    if "Nb_jours_max_reservation" not in equip_cols:
        c.execute("ALTER TABLE equipements ADD COLUMN Nb_jours_max_reservation INTEGER")
   


    # Table des utilisateurs
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        email TEXT UNIQUE,
        birthday TEXT,      
        validation INTEGER DEFAULT 0,
        intiales TEXT       
              
    )
''')
    # Table permessions



    c.execute('''
    CREATE TABLE IF NOT EXISTS user_equipment_write_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        equipment_id INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(equipment_id) REFERENCES equipments(id)
    )
''')
    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_user_equipment_write_perm
        ON user_equipment_write_permissions (user_id, equipment_id)
    """)
    # Table projet
    c.execute('''
    CREATE TABLE IF NOT EXISTS project (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Name_project TEXT NOT NULL,
        Name_Responsable TEXT
    )
''')
 # Table admin
    c.execute('''
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name_admin TEXT,
        email TEXT UNIQUE,
        notification INTEGER DEFAULT 0
    )
''')
    # Migration : ajoute la colonne 'notification' si la table 'admin' existait
    # deja sans cette colonne (bases creees avant l'ajout de la fonctionnalite).
    # 1 = cet admin recoit les emails "nouvel utilisateur a valider", 0 = non.
    c.execute("PRAGMA table_info(admin)")    # demande à SQLite la liste des colonnes actuelles de la table.
    admin_cols = [row[1] for row in c.fetchall()] # récupère juste les noms de ces colonnes
    if "notification" not in admin_cols: # Si notification n'est pas dans la table , il ajoute la colonne
        c.execute("ALTER TABLE admin ADD COLUMN notification INTEGER DEFAULT 0")

    # Table des réservations
    c.execute('''
        CREATE TABLE  IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipement_id INTEGER,
            user_id INTEGER,  
            user TEXT,
            start_time TEXT,
            end_time TEXT,
            comment TEXT,
            project TEXT,      
            FOREIGN KEY(equipement_id) REFERENCES equipements(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
)  
              
    ''')
 # Table des commentaires des admins
    c.execute('''
        CREATE TABLE  IF NOT EXISTS admin_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Comment TEXT,
            Name_admin TEXT,
            Bon INTEGER,
            Mauvais INTEGER,
            Warning INTEGER,
            Info INTEGER,
            Date_publication TEXT,
            Date_of_delete TEXT)  
    ''')
  # Table code admin
    c.execute('''
        CREATE TABLE  IF NOT EXISTS admin_code (
            id INTEGER PRIMARY KEY CHECK(id=1),  
            
            code TEXT
            )  
    ''')
    # Table des historiques de réservation-annulation
    c.execute('''
        CREATE TABLE  IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            history TEXT,
            date TEXT
            )  
    ''')

    

    conn.commit()
    conn.close()

   

