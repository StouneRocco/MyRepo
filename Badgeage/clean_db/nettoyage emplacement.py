from pymongo import MongoClient
import re

# ============================================================
# CONNEXION
# ============================================================

client = MongoClient("mongodb://localhost:27017/")

db = client["pfe"]

# Collection originale : NE SERA PAS MODIFIEE
collection_source = db["badgeage"]

# Nouvelles collections
collection_effectif = db["badgeage_effectif"]
collection_inutile = db["badgeage_inutile"]


# ============================================================
# LISTE DES EMPLACEMENTS A FORCER DANS "INUTILE"
# ============================================================

emplacements_forces_inutiles = [

    "9 ORGANISATION",
    "8 STAGIAIRE CESI",
    "8 ORGANISATION",
    "6 ORGANISATEUR",
    "36151326569943300",
    "36151326568566020",
    "36151326568096004",
    "36151326566980356",
    "36151004444957700",
    "36147066900721156",
    "36147066897501700",
    "36147066896988676",
    "36145230399822340",
    "36145230131244036",
    "36145229995705860",
    "36140620559626756",
    "36133282474172164",
    "36133282470627588",
    "36133282469923076",
    "36133282469911812",
    "36133282468272644",
    "36133282200243460",
    "3 ORGANISATION",
    "15 ORGANISATEUR",
    "14 ORGANISATION",
    "13 ORGANISATION",
    "12 ORGANISATION",
    "12 CESI",
    "11 CESI",
    "10 ORGANISATION",
    "1-pek aissotou",
    "1 ORGANISATION",

]


# ============================================================
# LISTE DES EMPLACEMENTS A FORCER DANS "EFFECTIF"
# ============================================================
#
# Ces emplacements seront placés dans badgeage_effectif
# même s'ils ne commencent PAS par un chiffre.
#

emplacements_forces_effectifs = [

    "vinci 2 Vinci Facilities",
    "Visio Castel porte principale_R.0_BP_I",
    "Visio Castel porte principale_R.0",
    "SS_sas ESEO_acces sud",
    "SS_sas ESEO_acces nord",
    "SS_acces esc B_ESTP",
    "SS_Local_Compresseur",
    "SS_LT_Ventilation ESTP",
    "SS_LT_TGBT ESTP",
    "SS_LT_SousStation ESTP",
    "SS-LT_Eau ESTP",
    "SPC",
    "S1-06-N_Local Tech_R-1_BP_I",
    "S1-05-S_Local TGBT_R-1_BP_I",
    "S1-04-S_Local SS-Station_R-1_BP_I",
    "S1-02-S_Local Ventil_R-1_BP_I",
    "RDR",
    "RDR",
    "R1_porte Déambul vers circul BIM",
    "R1_Circul BIM vers admin",
    "R1 circul. admin vers BIM C-01-02-S",
    "R0_Sortie_Portail_Coulissant VL/PL",
    "R0_Local Velo Int",
    "R0_Local Velo Ext",
    "R0_Ext_Local_debaras",
    "R-05-02-N.Terrasse_R.5",
    "R+5 Edicule technique CTA",
    "Portillon sortie VL/PL_R0_BP_I",
    "Portier Castel Portail VL/PL_R0_PORT",
    "Portier Castel Portail VL/PL_R0",
    "PC-SRT-EXPL03",
    "Local Vélo Int_R.0_BP_I",
    "Local Vélo Ext_R.0_BP_I",
    "Esc_B_ESTP_R0",
    "Esc B_RdC_ESEO",
    "Esc A_RdC_ESEO"
    "Entree SO carrefour",
    "Entree NE vers velo",
    "E-02-00-A.Palier_R.0_BP_I",
    "E-01-00-B.Palier _R.0_BP_I",
    "C010 hall vers Bureaux Chercheurs_NORD",
    "C009_Entree NO vers CTA et topo_R.0",
    "C003 hall vers PC_Securite_NORD_R0",
    "C001 BP sortie arriere SO vers VDI",
    "C00-37E-N.Labo topographie_R.0",
    "C-04-03_Admin ESEO vers Lobby_R.4",
    "C-04-02b_R+4 Asc vers Lobby",
    "C-04-02a_R4 admin ESEO vers Lobby",
    "C-04-01-S_R+4 lobby vers admin ESEO",
    "C-03-03-S.Cir_R.3 deambulation vers ESTP",
    "C-03-02-S.Circulation_R.3",
    "C-02-03-S.Circulation_R.2_BP_I",
    "C-02-03-S.Circulation_R.2",
    "C-00-07c-N.Circulation_R.0",
    "C-00-07b-N.Circulation_R.0_BP_I",
    "C-00-06-N.BP_I Sortie vers recherche",
    "C-00-04_Hall vers FabLab_R.0",
    "C-00-04_FabLab vers VDI_R.0",
    "C-00-03a circul LabLab sud ouest",
    "C-00-03 sortie vers C-00-13 VDI",
    "C-00-02a-S.Hall-deambulation_R.0",
    "C-00-02-S.FabLab vers Hall",
    "C-00-01-S Sas l Droite_R.0_PO_VT",
    "C-00-01-S Sas l Droite_R.0_BP_I",
    "C-00-01-S Sas Gauche_R.0_BP_I",
    "C-00-01-S Sas",
    "BP sortie arriere SO vers VDI",
    "Ascenseur sud - Étage 4",
    "Ascenseur sud - Étage 3",
    "Ascenseur sud - Étage 2",
    "Ascenseur sud - Étage 1",
    "Ascenseur sud - Sous-sol -1",
    "Ascenseur sud",
    "Ascenseur nord - Étage 4",
    "Ascenseur nord - Étage 3",
    "Ascenseur nord - Étage 2",
    "Ascenseur nord - Étage 1",
    "Ascenseur nord - Sous-sol -1",
    "Ascenseur nord",
    "Accès Parking VL_R-1",
    "Acces R0 escaliers S/Sol ESEO Nord",
    "Acces R0 escalier S/Sol ESTP Sud",
    "ACC1 R-1 33859571",
    "muscu",
    "RDR 00-37-N",
    "RDR 00-35-N",
    "Entree SO carrefour",

]


# ============================================================
# NORMALISATION DES LISTES
# ============================================================

emplacements_forces_inutiles = {
    str(emplacement).strip()
    for emplacement in emplacements_forces_inutiles
}

emplacements_forces_effectifs = {
    str(emplacement).strip()
    for emplacement in emplacements_forces_effectifs
}


# ============================================================
# DETECTION DES CONFLITS
# ============================================================

conflits = (
    emplacements_forces_inutiles
    & emplacements_forces_effectifs
)


if conflits:

    print()
    print("=" * 70)
    print("ATTENTION : CONFLIT DANS LES LISTES")
    print("=" * 70)
    print()

    for emplacement in sorted(conflits):
        print("-", emplacement)

    print()

    print(
        "Un même emplacement est présent dans les deux listes."
    )

    print(
        "Le script s'arrête pour éviter une classification ambiguë."
    )

    client.close()
    exit()


# ============================================================
# SUPPRESSION DES ANCIENNES COLLECTIONS
# ============================================================
#
# Cela ne touche PAS à badgeage0.
#

collection_effectif.drop()
collection_inutile.drop()


# ============================================================
# PARCOURS DES DOCUMENTS
# ============================================================

documents_effectif = []
documents_inutiles = []

documents_sans_emplacement = 0

documents_forces_effectifs = 0
documents_forces_inutiles = 0


for document in collection_source.find():

    emplacement = document.get("Emplacement")


    # ========================================================
    # EMPLACEMENT ABSENT
    # ========================================================

    if emplacement is None:

        documents_sans_emplacement += 1

        continue


    # ========================================================
    # NETTOYAGE
    # ========================================================

    emplacement = str(emplacement).strip()


    # ========================================================
    # EMPLACEMENT VIDE
    # ========================================================

    if emplacement == "":

        documents_sans_emplacement += 1

        continue


    # ========================================================
    # PRIORITE 1 :
    # FORCAGE VERS EFFECTIF
    # ========================================================

    if emplacement in emplacements_forces_effectifs:

        documents_effectif.append(document)

        documents_forces_effectifs += 1

        continue


    # ========================================================
    # PRIORITE 2 :
    # FORCAGE VERS INUTILE
    # ========================================================

    if emplacement in emplacements_forces_inutiles:

        documents_inutiles.append(document)

        documents_forces_inutiles += 1

        continue


    # ========================================================
    # PRIORITE 3 :
    # REGLE AUTOMATIQUE
    #
    # Commence par un chiffre -> EFFECTIF
    # Sinon -> INUTILE
    # ========================================================

    if re.match(r"^\d", emplacement):

        documents_effectif.append(document)

    else:

        documents_inutiles.append(document)


# ============================================================
# INSERTION DANS LES COLLECTIONS
# ============================================================

if documents_effectif:

    collection_effectif.insert_many(
        documents_effectif
    )


if documents_inutiles:

    collection_inutile.insert_many(
        documents_inutiles
    )


# ============================================================
# RESULTATS
# ============================================================

print()
print("=" * 70)
print("                 SEPARATION TERMINEE")
print("=" * 70)
print()

print(
    "Collection originale : badgeage0"
)

print()

print(
    "Documents dans badgeage_effectif :",
    len(documents_effectif)
)

print(
    "Documents dans badgeage_inutile  :",
    len(documents_inutiles)
)

print(
    "Documents sans emplacement       :",
    documents_sans_emplacement
)

print()

print(
    "Forcés vers EFFECTIF :",
    documents_forces_effectifs
)

print(
    "Forcés vers INUTILE  :",
    documents_forces_inutiles
)


# ============================================================
# LISTE EFFECTIF FORCEE
# ============================================================

print()
print("=" * 70)
print("        EMPLACEMENTS FORCES VERS EFFECTIF")
print("=" * 70)
print()

if emplacements_forces_effectifs:

    for emplacement in sorted(
        emplacements_forces_effectifs
    ):

        print("-", emplacement)

else:

    print("Aucun emplacement forcé vers effectif.")


# ============================================================
# LISTE INUTILE FORCEE
# ============================================================

print()
print("=" * 70)
print("        EMPLACEMENTS FORCES VERS INUTILE")
print("=" * 70)
print()

if emplacements_forces_inutiles:

    for emplacement in sorted(
        emplacements_forces_inutiles
    ):

        print("-", emplacement)

else:

    print("Aucun emplacement forcé vers inutile.")


# ============================================================
# RESUME
# ============================================================

print()
print("=" * 70)
print("                    COLLECTIONS")
print("=" * 70)
print()

print(
    "badgeage_effectif :",
    len(documents_effectif),
    "documents"
)

print(
    "badgeage_inutile  :",
    len(documents_inutiles),
    "documents"
)

print()

print(
    "La collection 'badgeage0' n'a pas été modifiée."
)


# ============================================================
# FERMETURE
# ============================================================

client.close()