from pathlib import Path
import math

import ifcopenshell
from ifcopenshell.util.placement import (
    get_local_placement,
    get_axis2placement,
)


# ============================================================
# FICHIER IFC
# ============================================================

# Cherche d'abord le modèle à côté de ce fichier (configuration locale),
# puis dans le dossier ../ifc utilisé par certains déploiements.
_IFC_FILENAME = "V7-CAMPUS-DIJON-BATIMENT.ifc"
_HERE = Path(__file__).resolve().parent
_CANDIDATE_PATHS = (
    _HERE / _IFC_FILENAME,
    _HERE / "ifc" / _IFC_FILENAME,
    _HERE.parent / "ifc" / _IFC_FILENAME,
)
IFC_PATH = next(
    (path for path in _CANDIDATE_PATHS if path.exists()),
    _CANDIDATE_PATHS[0],
)

_model = None


# ============================================================
# CHARGEMENT IFC
# ============================================================

def get_model():
    global _model

    if _model is None:

        if not IFC_PATH.exists():
            raise FileNotFoundError(
                f"Fichier IFC introuvable : {IFC_PATH}"
            )

        print(f"Chargement IFC : {IFC_PATH}")

        _model = ifcopenshell.open(str(IFC_PATH))

        print("IFC chargé avec succès.")

    return _model


# ============================================================
# INFORMATIONS GENERALES
# ============================================================

def get_building_info():

    model = get_model()

    return {
        "file": IFC_PATH.name,
        "project_count": len(model.by_type("IfcProject")),
        "building_count": len(model.by_type("IfcBuilding")),
        "storey_count": len(model.by_type("IfcBuildingStorey")),
        "space_count": len(model.by_type("IfcSpace")),
        "wall_count": len(model.by_type("IfcWall")),
        "door_count": len(model.by_type("IfcDoor")),
        "window_count": len(model.by_type("IfcWindow")),
    }


# ============================================================
# ETAGES
# ============================================================

def get_floors():

    model = get_model()

    floors = []

    for storey in model.by_type("IfcBuildingStorey"):

        elevation = storey.Elevation

        floors.append({
            "id": storey.id(),
            "name": storey.Name or f"Étage {storey.id()}",
            "elevation": float(elevation)
            if elevation is not None
            else None,
        })

    floors.sort(
        key=lambda floor: (
            floor["elevation"] is None,
            floor["elevation"]
            if floor["elevation"] is not None
            else 0,
        )
    )

    return floors


# ============================================================
# RECHERCHE ETAGE
# ============================================================

def _get_storey(floor_name):

    model = get_model()

    for storey in model.by_type("IfcBuildingStorey"):

        if storey.Name == floor_name:
            return storey

    return None


# ============================================================
# MATRICE IDENTITE
# ============================================================

def _identity_matrix():

    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


# ============================================================
# PLACEMENT GLOBAL
# ============================================================

def _get_placement_matrix(element):

    try:

        placement = element.ObjectPlacement

        if placement is None:
            return _identity_matrix()

        return get_local_placement(placement)

    except Exception as error:

        print(
            f"Placement impossible pour "
            f"{element.id()} : {error}"
        )

        return _identity_matrix()


# ============================================================
# TRANSFORMATION POINT
# ============================================================

def _transform_point(matrix, x, y):

    return {
        "x": float(
            matrix[0][0] * x
            + matrix[0][1] * y
            + matrix[0][3]
        ),

        "y": float(
            matrix[1][0] * x
            + matrix[1][1] * y
            + matrix[1][3]
        ),
    }


# ============================================================
# EXTRACTION POLYLINE
# ============================================================

def _polyline_points(curve, matrix):

    points = []

    try:

        if not curve:
            return points

        if not curve.is_a("IfcPolyline"):
            return points

        for point in curve.Points:

            coordinates = point.Coordinates

            if len(coordinates) < 2:
                continue

            p = _transform_point(
                matrix,
                float(coordinates[0]),
                float(coordinates[1])
            )

            points.append(p)

    except Exception:
        pass

    return points


# ============================================================
# EXTRACTION CURVE
# ============================================================

def _curve_points(curve, matrix):

    if curve is None:
        return []

    # -------------------------------
    # POLYLINE
    # -------------------------------

    if curve.is_a("IfcPolyline"):

        return _polyline_points(
            curve,
            matrix
        )

    # -------------------------------
    # COMPOSITE CURVE
    # -------------------------------

    if curve.is_a("IfcCompositeCurve"):

        result = []

        for segment in curve.Segments:

            parent = segment.ParentCurve

            result.extend(
                _curve_points(
                    parent,
                    matrix
                )
            )

        return result

    return []


# ============================================================
# EXTRACTION AXE IFC
# ============================================================

def _extract_axis_points(element):

    try:

        axis = getattr(
            element,
            "Axis",
            None
        )

        if axis is None:
            return []

        matrix = _get_placement_matrix(
            element
        )

        return _curve_points(
            axis,
            matrix
        )

    except Exception:

        return []


# ============================================================
# EXTRACTION REPRESENTATION 2D
# ============================================================

def _extract_representation_points(element):

    points = []

    try:

        representation = element.Representation

        if representation is None:
            return []

        matrix = _get_placement_matrix(
            element
        )

        for rep in representation.Representations:

            identifier = getattr(
                rep,
                "RepresentationIdentifier",
                None
            )

            rep_type = getattr(
                rep,
                "RepresentationType",
                None
            )

            # On privilégie les représentations
            # utiles pour une vue plan.

            if (
                identifier not in [
                    "Plan",
                    "FootPrint",
                    "Axis"
                ]
                and
                rep_type not in [
                    "Curve2D",
                    "GeometricCurveSet",
                ]
            ):
                continue

            for item in rep.Items:

                if item.is_a("IfcPolyline"):

                    points.extend(
                        _polyline_points(
                            item,
                            matrix
                        )
                    )

                elif item.is_a(
                    "IfcCompositeCurve"
                ):

                    points.extend(
                        _curve_points(
                            item,
                            matrix
                        )
                    )

    except Exception:
        pass

    return points


# ============================================================
# EXTRACTION GEOMETRIE 2D
# ============================================================

def _extract_points(element):

    # 1. Pour les murs :
    #    on essaie d'abord Axis

    axis_points = _extract_axis_points(
        element
    )

    if len(axis_points) >= 2:
        return axis_points

    # 2. Sinon représentation 2D

    representation_points = (
        _extract_representation_points(
            element
        )
    )

    if len(representation_points) >= 2:
        return representation_points

    return []


# ============================================================
# GEOMETRIE 2D EXACTE DES ESPACES IFC
# ============================================================

def _multiply_matrices(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _axis2placement_matrix(placement):
    if placement is None:
        return _identity_matrix()
    try:
        return get_axis2placement(placement)
    except Exception:
        return _identity_matrix()


def _dedupe_points(points, tolerance=0.001):
    if not points:
        return []
    result = [points[0]]
    for point in points[1:]:
        prev = result[-1]
        if math.hypot(point["x"]-prev["x"], point["y"]-prev["y"]) > tolerance:
            result.append(point)
    if len(result) > 1 and math.hypot(result[0]["x"]-result[-1]["x"], result[0]["y"]-result[-1]["y"]) <= tolerance:
        result.pop()
    return result


def _ring_area(points):
    if len(points) < 3:
        return 0.0
    return sum(points[i]["x"]*points[(i+1)%len(points)]["y"] - points[(i+1)%len(points)]["x"]*points[i]["y"] for i in range(len(points))) / 2.0


def _normalize_ring(points):
    # Nettoyage uniquement : surtout PAS de convex hull.
    points = _dedupe_points(points)
    if len(points) < 3 or abs(_ring_area(points)) < 1e-9:
        return []
    return points


def _indexed_polycurve_points(curve, matrix):
    try:
        coords = getattr(getattr(curve, "Points", None), "CoordList", None)
        if coords is None:
            return []
        return [_transform_point(matrix, float(c[0]), float(c[1])) for c in coords if len(c) >= 2]
    except Exception:
        return []


def _profile_curve_points(curve, matrix):
    if curve is None:
        return []
    if curve.is_a("IfcPolyline"):
        return _polyline_points(curve, matrix)
    if curve.is_a("IfcIndexedPolyCurve"):
        return _indexed_polycurve_points(curve, matrix)
    if curve.is_a("IfcCompositeCurve"):
        result=[]
        for segment in curve.Segments:
            result.extend(_profile_curve_points(segment.ParentCurve, matrix))
        return result
    return []


def _rectangle_profile_points(profile, matrix):
    try:
        w=float(profile.XDim); h=float(profile.YDim)
    except Exception:
        return []
    pts=[(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]
    return [_transform_point(matrix,x,y) for x,y in pts]


def _circle_profile_points(profile, matrix, segments=48):
    try:
        r=float(profile.Radius)
    except Exception:
        return []
    return [_transform_point(matrix, r*math.cos(2*math.pi*i/segments), r*math.sin(2*math.pi*i/segments)) for i in range(segments)]


def _extract_profile_rings(profile, matrix):
    if profile is None:
        return []
    try:
        if profile.is_a("IfcRectangleProfileDef"):
            pts=_rectangle_profile_points(profile,matrix)
            return [pts] if len(pts)>=3 else []
        if profile.is_a("IfcCircleProfileDef"):
            pts=_circle_profile_points(profile,matrix)
            return [pts] if len(pts)>=3 else []
        if profile.is_a("IfcArbitraryClosedProfileDef"):
            pts=_normalize_ring(_profile_curve_points(getattr(profile,"OuterCurve",None),matrix))
            return [pts] if len(pts)>=3 else []
        if profile.is_a("IfcArbitraryProfileDefWithVoids"):
            rings=[]
            outer=_normalize_ring(_profile_curve_points(getattr(profile,"OuterCurve",None),matrix))
            if len(outer)>=3: rings.append(outer)
            for inner in getattr(profile,"InnerCurves",None) or []:
                hole=_normalize_ring(_profile_curve_points(inner,matrix))
                if len(hole)>=3: rings.append(hole)
            return rings
    except Exception as error:
        print(f"Profil IFC impossible à extraire : {error}")
    return []


def _extract_space_profile(space):
    """Extrait le vrai contour 2D du IfcSpace, sans enveloppe convexe."""
    try:
        representation=getattr(space,"Representation",None)
        if representation is None:
            return []
        space_matrix=_get_placement_matrix(space)
        for rep in representation.Representations:
            for item in getattr(rep,"Items",None) or []:
                profile=getattr(item,"SweptArea",None)
                if profile is None:
                    continue
                solid_matrix=_axis2placement_matrix(getattr(item,"Position",None))
                profile_matrix=_axis2placement_matrix(getattr(profile,"Position",None))
                matrix=_multiply_matrices(space_matrix,_multiply_matrices(solid_matrix,profile_matrix))
                rings=_extract_profile_rings(profile,matrix)
                if rings:
                    return rings
    except Exception as error:
        print(f"Profil 2D indisponible pour IfcSpace #{space.id()} : {error}")
    return []


def _extract_space_curve_fallback(space):
    """Fallback 2D explicite, sans convex hull."""
    try:
        representation=getattr(space,"Representation",None)
        if representation is None:
            return []
        matrix=_get_placement_matrix(space)
        for rep in representation.Representations:
            identifier=getattr(rep,"RepresentationIdentifier",None)
            rep_type=getattr(rep,"RepresentationType",None)
            if identifier not in ["Plan","FootPrint"] and rep_type not in ["Curve2D","GeometricCurveSet"]:
                continue
            for item in rep.Items:
                if item.is_a("IfcPolyline"):
                    pts=_polyline_points(item,matrix)
                elif item.is_a("IfcIndexedPolyCurve"):
                    pts=_indexed_polycurve_points(item,matrix)
                elif item.is_a("IfcCompositeCurve"):
                    pts=_profile_curve_points(item,matrix)
                else:
                    pts=[]
                pts=_normalize_ring(pts)
                if len(pts)>=3:
                    return [pts]
    except Exception:
        pass
    return []


# ============================================================
# CREATION LIGNES
# ============================================================

def _points_to_lines(points):

    lines = []

    if len(points) < 2:
        return lines

    for i in range(
        len(points) - 1
    ):

        p1 = points[i]
        p2 = points[i + 1]

        lines.append({

            "x1": p1["x"],
            "y1": p1["y"],

            "x2": p2["x"],
            "y2": p2["y"],

        })

    return lines


# ============================================================
# POSITION D'UN OBJET
# ============================================================

def _get_object_position(element):

    try:

        matrix = _get_placement_matrix(
            element
        )

        return {
            "x": float(matrix[0][3]),
            "y": float(matrix[1][3]),
        }

    except Exception:

        return None


# ============================================================
# DIMENSIONS DEPUIS LE NOM
# ============================================================

def _get_dimensions_from_name(name):

    if not name:
        return {
            "width": 80.0,
            "height": 200.0,
        }

    # Exemple de noms IFC :
    #
    # 90x205
    # 120x250
    # 140x220

    import re

    match = re.search(
        r"(\d+(?:[.,]\d+)?)x(\d+(?:[.,]\d+)?)",
        name
    )

    if match:

        try:

            width = float(
                match.group(1).replace(",", ".")
            )

            height = float(
                match.group(2).replace(",", ".")
            )

            return {
                "width": width,
                "height": height,
            }

        except Exception:
            pass

    return {
        "width": 80.0,
        "height": 200.0,
    }


# ============================================================
# EXTRACTION ELEMENT
# ============================================================

def _extract_element(
    element,
    element_type
):

    points = _extract_points(
        element
    )

    # --------------------------------------------------------
    # VRAIE GEOMETRIE
    # --------------------------------------------------------

    if len(points) >= 2:

        lines = _points_to_lines(
            points
        )

        return {

            "id": element.id(),

            "type": element_type,

            "name": element.Name,

            "lines": lines,

            "position": {
                "x": points[0]["x"],
                "y": points[0]["y"],
            },

        }

    # --------------------------------------------------------
    # POSITION
    # --------------------------------------------------------

    position = _get_object_position(
        element
    )

    if position is None:
        return None

    dimensions = (
        _get_dimensions_from_name(
            element.Name
        )
    )

    return {

        "id": element.id(),

        "type": element_type,

        "name": element.Name,

        "lines": [],

        "position": position,

        "width": dimensions["width"],

        "height": dimensions["height"],

    }


# ============================================================
# APPARTENANCE A UN ETAGE
# ============================================================

def _belongs_to_storey(element, storey_id):
    """Vérifie le rattachement IFC direct ou via la hiérarchie spatiale."""
    try:
        pending = []
        for rel in (getattr(element, "ContainedInStructure", None) or []):
            parent = getattr(rel, "RelatingStructure", None)
            if parent is not None:
                pending.append(parent)
        visited = set()
        while pending:
            parent = pending.pop()
            pid = parent.id()
            if pid == storey_id:
                return True
            if pid in visited:
                continue
            visited.add(pid)
            for rel in (getattr(parent, "Decomposes", None) or []):
                ancestor = getattr(rel, "RelatingObject", None)
                if ancestor is not None:
                    pending.append(ancestor)
        # Cas de l'espace directement décomposé par l'étage.
        for storey in get_model().by_type("IfcBuildingStorey"):
            if storey.id() == storey_id:
                for rel in (getattr(storey, "IsDecomposedBy", None) or []):
                    if any(getattr(obj, "id", lambda: -1)() == element.id()
                           for obj in (getattr(rel, "RelatedObjects", None) or [])):
                        return True
                break
    except Exception:
        pass
    return False


# ============================================================
# EXTRACTION ESPACE
# ============================================================

def _extract_space(space):
    """Extrait une salle comme une zone 2D indépendante et exploitable par une heatmap."""
    code=_clean_ifc_text(getattr(space,"Name",None))
    long_name=_clean_ifc_text(getattr(space,"LongName",None))
    description=_clean_ifc_text(getattr(space,"Description",None))
    if not code:
        code=_clean_ifc_text(getattr(space,"Identification",None))

    rings=_extract_space_profile(space)
    if not rings:
        rings=_extract_space_curve_fallback(space)

    # Ne jamais remplacer une salle inconnue par une grande enveloppe approximative.
    if not rings:
        print(f"IfcSpace #{space.id()} : aucun contour 2D fiable trouvé. Espace ignoré.")
        return None

    outer=_normalize_ring(rings[0])
    if len(outer)<3:
        return None

    holes=[]
    for ring in rings[1:]:
        ring=_normalize_ring(ring)
        if len(ring)>=3:
            holes.append(ring)

    area2=0.0; cx=0.0; cy=0.0
    for i,p in enumerate(outer):
        q=outer[(i+1)%len(outer)]
        cross=p["x"]*q["y"]-q["x"]*p["y"]
        area2+=cross
        cx+=(p["x"]+q["x"])*cross
        cy+=(p["y"]+q["y"])*cross

    if abs(area2)>1e-9:
        position={"x":cx/(3.0*area2),"y":cy/(3.0*area2)}
    else:
        position={"x":sum(p["x"] for p in outer)/len(outer),"y":sum(p["y"] for p in outer)/len(outer)}

    room_name=long_name or description or code or f"Salle {space.id()}"

    # points = contour exact pour le frontend actuel.
    # holes = éventuels évidements IFC, conservés pour la heatmap future.
    return {
        "id":space.id(),
        "type":"space",
        "name":code or room_name,
        "code":code or "",
        "longName":long_name or room_name,
        "long_name":long_name or room_name,
        "roomName":room_name,
        "description":description or "",
        "points":outer,
        "holes":holes,
        "lines":[{"x1":outer[i]["x"],"y1":outer[i]["y"],"x2":outer[(i+1)%len(outer)]["x"],"y2":outer[(i+1)%len(outer)]["y"]} for i in range(len(outer))],
        "position":position,
        "area":abs(_ring_area(outer)),
    }


def _clean_ifc_text(value):
    """Nettoie les chaînes IFC sans perdre les codes de locaux."""
    if value is None:
        return ""
    text = " ".join(str(value).replace("\x00", "").split())
    return "" if text.lower() in {"none", "null", "n/a"} else text


# ============================================================
# EXTRACTION D'UN ETAGE
# ============================================================

def get_floor_geometry(
    floor_name
):

    model = get_model()

    storey = _get_storey(
        floor_name
    )

    if storey is None:

        raise ValueError(
            f"Niveau IFC introuvable : "
            f"{floor_name}"
        )

    print()
    print(
        "=========================================="
    )
    print(
        f"Extraction IFC : {floor_name}"
    )
    print(
        "=========================================="
    )

    storey_id = storey.id()

    elements = []
    spaces = []


    # ========================================================
    # MURS
    # ========================================================

    for wall in model.by_type(
        "IfcWall"
    ):

        if not _belongs_to_storey(
            wall,
            storey_id
        ):
            continue

        result = _extract_element(
            wall,
            "wall"
        )

        if result:

            elements.append(
                result
            )


    # ========================================================
    # PORTES
    # ========================================================

    for door in model.by_type(
        "IfcDoor"
    ):

        if not _belongs_to_storey(
            door,
            storey_id
        ):
            continue

        result = _extract_element(
            door,
            "door"
        )

        if result:

            elements.append(
                result
            )


    # ========================================================
    # FENETRES
    # ========================================================

    for window in model.by_type(
        "IfcWindow"
    ):

        if not _belongs_to_storey(
            window,
            storey_id
        ):
            continue

        result = _extract_element(
            window,
            "window"
        )

        if result:

            elements.append(
                result
            )


    # ========================================================
    # ESPACES / SALLES
    # ========================================================

    for space in model.by_type(
        "IfcSpace"
    ):

        if not _belongs_to_storey(
            space,
            storey_id
        ):
            continue

        result = _extract_space(
            space
        )

        if result:

            spaces.append(
                result
            )


    # ========================================================
    # CALCUL DES BOUNDS
    # ========================================================

    all_points = []

    for element in elements:

        for line in element.get(
            "lines",
            []
        ):

            all_points.append({
                "x": line["x1"],
                "y": line["y1"],
            })

            all_points.append({
                "x": line["x2"],
                "y": line["y2"],
            })

        position = element.get(
            "position"
        )

        # IMPORTANT :
        # on n'ajoute pas toutes les positions
        # au calcul des bounds.
        #
        # Certains objets IFC ont des placements
        # aberrants / locaux.
        #
        # Les murs donnent les bounds principaux.

    for space in spaces:

        for line in space.get(
            "lines",
            []
        ):

            all_points.append({
                "x": line["x1"],
                "y": line["y1"],
            })

            all_points.append({
                "x": line["x2"],
                "y": line["y2"],
            })


    # ========================================================
    # FALLBACK SI PAS DE LIGNES
    # ========================================================

    if not all_points:

        positions = []

        for element in elements:

            position = element.get(
                "position"
            )

            if position:
                positions.append(
                    position
                )

        if positions:

            all_points = positions


    # ========================================================
    # AUCUNE GEOMETRIE
    # ========================================================

    if not all_points:

        print(
            f"Aucune géométrie trouvée "
            f"pour {floor_name}."
        )

        return {

            "floor": {

                "id":
                    storey.id(),

                "name":
                    storey.Name,

                "elevation":
                    storey.Elevation,

            },

            "bounds": None,

            "elements":
                elements,

            "spaces":
                spaces,

        }


    # ========================================================
    # BOUNDS
    # ========================================================

    xs = [
        point["x"]
        for point in all_points
    ]

    ys = [
        point["y"]
        for point in all_points
    ]

    min_x = min(xs)
    max_x = max(xs)

    min_y = min(ys)
    max_y = max(ys)

    width = max_x - min_x
    height = max_y - min_y


    # Petite marge

    margin_x = (
        width * 0.03
        if width > 0
        else 100
    )

    margin_y = (
        height * 0.03
        if height > 0
        else 100
    )


    min_x -= margin_x
    max_x += margin_x

    min_y -= margin_y
    max_y += margin_y

    width = max_x - min_x
    height = max_y - min_y


    # ========================================================
    # COMPTEURS
    # ========================================================

    wall_count = len([
        e for e in elements
        if e["type"] == "wall"
    ])

    door_count = len([
        e for e in elements
        if e["type"] == "door"
    ])

    window_count = len([
        e for e in elements
        if e["type"] == "window"
    ])


    print(
        f"Extraction terminée : {floor_name}"
    )

    print(
        f"Murs      : {wall_count}"
    )

    print(
        f"Portes    : {door_count}"
    )

    print(
        f"Fenêtres  : {window_count}"
    )

    print(
        f"Espaces   : {len(spaces)}"
    )

    print(
        f"Bounds    : "
        f"{width:.1f} x {height:.1f}"
    )


    # ========================================================
    # RESULTAT API
    # ========================================================

    return {

        "floor": {

            "id":
                storey.id(),

            "name":
                storey.Name,

            "elevation":
                storey.Elevation,

        },

        "bounds": {

            "min_x":
                min_x,

            "max_x":
                max_x,

            "min_y":
                min_y,

            "max_y":
                max_y,

            "width":
                width,

            "height":
                height,

        },

        "elements":
            elements,

        "spaces":
            spaces,

    }