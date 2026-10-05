import ifcopenshell

def extraire_salles_ifc(ifc_path, txt_out="salles_par_etage.txt"):
    model = ifcopenshell.open(ifc_path)
    storeys = model.by_type("IfcBuildingStorey")

    # Trier les étages par altitude (Elevation)
    storeys.sort(key=lambda s: getattr(s, "Elevation", 0) or 0)

    lignes = []

    for storey in storeys:
        nom_etage = storey.Name or "Étage sans nom"
        lignes.append(f"=== ÉTAGE : {nom_etage} ===")

        salles = []

        # 1. Recherche via agrégation (RelAggregates)
        for rel in getattr(storey, "IsDecomposedBy", []):
            for obj in rel.RelatedObjects:
                if obj.is_a("IfcSpace"):
                    salles.append(obj)

        # 2. Recherche via contenu spatial (RelContainedInSpatialStructure)
        for rel in getattr(storey, "ContainsElements", []):
            for elem in rel.RelatedElements:
                if elem.is_a("IfcSpace") and elem not in salles:
                    salles.append(elem)

        if not salles:
            lignes.append("  (Aucune salle répertoriée)")
        else:
            # Trier les salles par leur code
            salles.sort(key=lambda s: s.Name or "")
            for s in salles:
                code = s.Name or "SANS_CODE"
                nom = s.LongName or "Sans nom"
                lignes.append(f"  - [{code}] {nom}")

        lignes.append("")  # Ligne vide de séparation

    contenu = "\n".join(lignes)

    # Sauvegarde dans le fichier texte
    with open(txt_out, "w", encoding="utf-8") as f:
        f.write(contenu)

    print(f"Extraction terminée ! Fichier créé : {txt_out}")

if __name__ == "__main__":
    extraire_salles_ifc("V7-CAMPUS-DIJON-BATIMENT.ifc")