from __future__ import annotations

import argparse
import html
import math
import re
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

from ifc_service import get_floor_geometry, get_floors


DEFAULT_OUTPUT = "exports"
EXCLUDED_FLOORS = {"T1", "Acrotère"}

# ------------------------------------------------------------------
# Espaces IFC qui sont connus comme zones globales / techniques,
# pas comme des salles indépendantes.
# ------------------------------------------------------------------
CONTAINER_NAME_PATTERNS = (
    "COMMUN",
    "ESTP",
)

CONTAINER_CODE_PATTERNS = (
    "VB:",
)

# Un espace beaucoup plus grand que les vrais locaux et qui porte
# un nom générique est considéré comme conteneur.
CONTAINER_AREA_FACTOR = 12.0

# Un espace candidat n'est isolé que s'il recouvre réellement
# d'autres espaces plus petits. Cela évite de casser une grande
# vraie salle simplement parce qu'elle est grande.
ISOLATION_MIN_CHILDREN = 1
ISOLATION_AREA_RATIO = 1.15

# Pour éviter deux fois exactement la même zone.
GEOMETRY_ROUND = 2


# ------------------------------------------------------------------
# Apparence
# ------------------------------------------------------------------

BG = "#07101d"
SPACE_FILL = "#263e57"
SPACE_STROKE = "#577da3"
CONTAINER_STROKE = "#31465d"
WALL_STROKE = "#e8f1fb"
DOOR_STROKE = "#58d68d"
WINDOW_STROKE = "#55b7ff"
TEXT_COLOR = "#ffffff"
CODE_COLOR = "#b9d9ff"


# ==================================================================
# Utilitaires
# ==================================================================

def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def clean(value: Any) -> str:
    if value is None:
        return ""

    value = re.sub(r"\s+", " ", str(value)).strip()

    if value.lower() in {"none", "null", "n/a"}:
        return ""

    return value


def norm_text(value: Any) -> str:
    return clean(value).upper()


def safe_id(value: Any) -> str:
    value = clean(value)
    value = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value)

    if not value:
        value = "unknown"

    return value


def normalize_point(
    point: dict[str, Any],
    bounds: dict[str, Any],
) -> tuple[float, float]:

    return (
        float(point["x"]) - float(bounds["min_x"]),
        float(bounds["max_y"]) - float(point["y"]),
    )


def normalize_line(
    line: dict[str, Any],
    bounds: dict[str, Any],
) -> tuple[float, float, float, float]:

    x1, y1 = normalize_point(
        {"x": line["x1"], "y": line["y1"]},
        bounds,
    )

    x2, y2 = normalize_point(
        {"x": line["x2"], "y": line["y2"]},
        bounds,
    )

    return x1, y1, x2, y2


def polygon_centroid(
    points: list[tuple[float, float]],
) -> tuple[float, float] | None:

    if len(points) < 3:
        return None

    twice_area = 0.0
    cx = 0.0
    cy = 0.0

    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]

        cross = x1 * y2 - x2 * y1

        twice_area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross

    if abs(twice_area) < 1e-9:
        return (
            sum(x for x, _ in points) / len(points),
            sum(y for _, y in points) / len(points),
        )

    return (
        cx / (3.0 * twice_area),
        cy / (3.0 * twice_area),
    )


# ==================================================================
# Géométrie
# ==================================================================

def get_space_points(
    space: dict[str, Any],
    bounds: dict[str, Any],
) -> list[tuple[float, float]]:

    raw = space.get("points") or []

    if len(raw) < 3:
        lines = space.get("lines") or []

        if len(lines) >= 3:
            raw = [
                {
                    "x": line["x1"],
                    "y": line["y1"],
                }
                for line in lines
            ]

    return [
        normalize_point(point, bounds)
        for point in raw
    ]


def get_space_holes(
    space: dict[str, Any],
    bounds: dict[str, Any],
) -> list[list[tuple[float, float]]]:

    holes = []

    for ring in space.get("holes") or []:

        if len(ring) < 3:
            continue

        holes.append([
            normalize_point(point, bounds)
            for point in ring
        ])

    return holes


def ring_path(
    points: list[tuple[float, float]],
) -> str:

    if len(points) < 3:
        return ""

    return (
        "M "
        + " L ".join(
            f"{x:.3f} {y:.3f}"
            for x, y in points
        )
        + " Z"
    )


def make_space_path(
    space: dict[str, Any],
    bounds: dict[str, Any],
) -> tuple[str, list[tuple[float, float]]]:

    points = get_space_points(space, bounds)

    if len(points) < 3:
        return "", []

    parts = [ring_path(points)]

    for hole in get_space_holes(space, bounds):

        path = ring_path(hole)

        if path:
            parts.append(path)

    return " ".join(parts), points


def geometry_key(
    space: dict[str, Any],
    bounds: dict[str, Any],
) -> str:

    """
    Clé géométrique pour supprimer les doublons exacts ou quasi exacts.

    On trie les coordonnées pour que le sens de parcours du contour
    n'ait pas d'importance.
    """

    points = get_space_points(space, bounds)

    if len(points) < 3:
        return ""

    rounded = sorted(
        (
            round(x, GEOMETRY_ROUND),
            round(y, GEOMETRY_ROUND),
        )
        for x, y in points
    )

    return repr(rounded)


# ==================================================================
# Isolation géométrique des espaces recouvrants
# ==================================================================

def polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def point_in_polygon(
    point: tuple[float, float],
    polygon: list[tuple[float, float]],
) -> bool:
    """Test point-dans-polygone simple, sans dépendance externe."""
    if len(polygon) < 3:
        return False

    x, y = point
    inside = False

    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        intersects = (
            (yi > y) != (yj > y)
            and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-30) + xi
        )

        if intersects:
            inside = not inside

        j = i

    return inside


def bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_contains(
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
    tolerance: float = 1.0,
) -> bool:
    return (
        inner[0] >= outer[0] - tolerance
        and inner[1] >= outer[1] - tolerance
        and inner[2] <= outer[2] + tolerance
        and inner[3] <= outer[3] + tolerance
    )


def shapely_to_svg_path(geometry) -> str:
    """Convertit une géométrie Shapely en chemin SVG avec trous."""
    if geometry is None or geometry.is_empty:
        return ""

    polygons = []
    if isinstance(geometry, Polygon):
        polygons = [geometry]
    elif isinstance(geometry, MultiPolygon):
        polygons = list(geometry.geoms)
    else:
        # GeometryCollection / autres : on ne conserve que les polygones.
        polygons = [g for g in getattr(geometry, "geoms", []) if isinstance(g, Polygon)]

    parts = []
    for poly in polygons:
        ext = list(poly.exterior.coords)
        if len(ext) >= 4:
            parts.append(ring_path([(float(x), float(y)) for x, y in ext[:-1]]))

        for interior in poly.interiors:
            ring = list(interior.coords)
            if len(ring) >= 4:
                parts.append(ring_path([(float(x), float(y)) for x, y in ring[:-1]]))

    return " ".join(part for part in parts if part)


def polygon_from_points(points: list[tuple[float, float]]):
    if len(points) < 3:
        return None
    poly = Polygon(points)
    if poly.is_empty or poly.area <= 0:
        return None
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly if not poly.is_empty and poly.area > 0 else None


def build_exclusive_suspect_geometries(
    all_spaces: list[dict[str, Any]],
    bounds: dict[str, Any],
) -> dict[str, Any]:
    """Construit UNE fois la partition exclusive des espaces suspects.

    C'est le point essentiel pour la heatmap : deux espaces suspects ne
    peuvent jamais recevoir la même portion géométrique.

    On attribue les intersections selon une priorité déterministe :
    - petite surface d'abord ;
    - puis ID IFC pour départager les égalités.

    Pour chaque suspect, sa géométrie devient :
        suspect - tous les suspects déjà attribués - salles normales

    Le résultat est réutilisé à la fois pour le dessin SVG et les clipPath,
    afin que l'affichage et la heatmap utilisent exactement la même zone.
    """
    suspect_items: list[tuple[str, Any, float]] = []

    for space in all_spaces:
        if not is_suspected_container(space):
            continue
        points = get_space_points(space, bounds)
        poly = polygon_from_points(points)
        if poly is None:
            continue
        sid = str(space.get("id", ""))
        suspect_items.append((sid, poly, float(poly.area)))

    # Chaque suspect reçoit son propre morceau. Une intersection entre
    # plusieurs suspects est attribuée au premier selon cet ordre.
    suspect_items.sort(key=lambda item: (item[2], item[0]))

    exclusive: dict[str, Any] = {}
    already_assigned = None

    for sid, poly, _area in suspect_items:
        try:
            if already_assigned is None:
                own = poly
            else:
                own = poly.difference(already_assigned)

            # On ne réserve que la géométrie effectivement attribuée à ce
            # suspect. Ainsi les suspects suivants ne pourront plus utiliser
            # cette même surface.
            if not own.is_empty and own.area > 0:
                exclusive[sid] = own
                already_assigned = own if already_assigned is None else unary_union(
                    [already_assigned, own]
                )
            else:
                exclusive[sid] = own
        except Exception:
            # Sécurité : en cas de géométrie Shapely problématique, on garde
            # au minimum le polygone individuel au lieu de supprimer l'espace.
            exclusive[sid] = poly
            already_assigned = poly if already_assigned is None else unary_union(
                [already_assigned, poly]
            )

    return exclusive


def isolated_path_data(
    space: dict[str, Any],
    bounds: dict[str, Any],
    all_spaces: list[dict[str, Any]],
    exclusive_suspects: dict[str, Any] | None = None,
) -> tuple[str, int]:
    """Retourne la géométrie exclusive d'un espace.

    Les espaces normaux conservent leur contour IFC exact.
    Les espaces suspects utilisent la partition exclusive construite
    collectivement : aucune surface commune entre suspects ne peut donc
    être présente dans plusieurs clipPath de heatmap.
    """
    points = get_space_points(space, bounds)
    if len(points) < 3:
        return "", 0

    original_path, _ = make_space_path(space, bounds)

    if not is_suspected_container(space):
        return original_path, 0

    sid = str(space.get("id", ""))
    parent = None

    if exclusive_suspects is not None:
        parent = exclusive_suspects.get(sid)

    if parent is None:
        parent = polygon_from_points(points)

    if parent is None or parent.is_empty:
        return original_path, 0

    isolated = parent
    isolated_children = 0

    # Les salles normales restent visibles et doivent donc être retirées
    # de la surface du suspect. IMPORTANT : on ne retire jamais un autre
    # suspect ici ; cette séparation a déjà été faite par la partition
    # exclusive ci-dessus.
    normal_children = []
    for other in all_spaces:
        if other.get("id") == space.get("id"):
            continue
        if is_suspected_container(other):
            continue

        other_points = get_space_points(other, bounds)
        if len(other_points) < 3:
            continue
        other_poly = polygon_from_points(other_points)
        if other_poly is None:
            continue

        try:
            intersection = parent.intersection(other_poly)
            if intersection.is_empty:
                continue

            ratio = intersection.area / max(other_poly.area, 1e-9)
            if ratio >= 0.90:
                normal_children.append(other_poly)
                isolated_children += 1
        except Exception:
            continue

    try:
        if normal_children and not isolated.is_empty:
            isolated = isolated.difference(unary_union(normal_children))

        path = shapely_to_svg_path(isolated)
        if path:
            return path, isolated_children
    except Exception:
        pass

    return original_path, isolated_children


# ==================================================================
# Classification des espaces
# ==================================================================

def space_label(space: dict[str, Any]) -> str:
    return clean(
        space.get("roomName")
        or space.get("longName")
        or space.get("name")
    )


def is_suspected_container(space: dict[str, Any]) -> bool:
    """
    Détecte seulement un espace potentiellement global pour le marquer
    dans le SVG. IMPORTANT : il n'est jamais supprimé.

    Cette version est volontairement conservatrice : une grande salle
    ou une salle nommée COMMUN/ESTP reste une vraie zone sélectionnable.
    """
    name = norm_text(space_label(space))
    code = norm_text(space.get("code"))

    return (
        any(pattern in name for pattern in CONTAINER_NAME_PATTERNS)
        or any(pattern in code for pattern in CONTAINER_CODE_PATTERNS)
    )


def classify_spaces(
    spaces: list[dict[str, Any]],
    bounds: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Version non-agressive.

    Toutes les géométries IfcSpace fiables sont conservées comme zones
    sélectionnables. On ne supprime plus les grands espaces et on ne
    dédoublonne plus les contours : l'ID IFC reste ainsi toujours
    disponible pour l'affectation d'un capteur.

    Les espaces potentiellement globaux sont simplement retournés dans
    ``containers`` à titre informatif. Ils sont néanmoins dessinés dans
    la couche principale, derrière les petites salles.
    """
    valid = [
        space
        for space in spaces
        if len(get_space_points(space, bounds)) >= 3
    ]

    containers = [
        space for space in valid
        if is_suspected_container(space)
    ]

    # Les grandes surfaces passent derrière les petites.
    # Cela conserve leur géométrie sans leur permettre de recouvrir
    # visuellement toutes les salles détaillées.
    rooms = sorted(
        valid,
        key=lambda space: float(space.get("area") or 0),
        reverse=True,
    )

    return rooms, containers


# ==================================================================
# SVG : salles
# ==================================================================

def draw_room(
    space: dict[str, Any],
    bounds: dict[str, Any],
    all_spaces: list[dict[str, Any]],
    exclusive_suspects: dict[str, Any] | None = None,
) -> str:

    d, isolated_children = isolated_path_data(
        space,
        bounds,
        all_spaces,
        exclusive_suspects,
    )

    if not d:
        return ""

    raw_id = space.get("id", "")
    sid = safe_id(raw_id)

    code = clean(space.get("code"))
    name = space_label(space)
    area = space.get("area")

    return (
        f'<path '
        f'id="space-{sid}" '
        f'class="ifc-space" '
        f'd="{d}" '
        f'fill-rule="evenodd" '
        f'clip-rule="evenodd" '
        f'data-space-id="{esc(raw_id)}" '
        f'data-code="{esc(code)}" '
        f'data-room-name="{esc(name)}" '
        f'data-area="{esc(area if area is not None else "")}" '
        f'data-layer="space" '
        f'data-selectable="true" '
        f'data-heatmap-target="space-{sid}" '
        f'data-clip-path="clip-space-{sid}" '
        f'data-suspected-container="{str(is_suspected_container(space)).lower()}" '
        f'data-isolated-children="{isolated_children}" '
        f'/>\n'
    )


def draw_room_clip(
    space: dict[str, Any],
    bounds: dict[str, Any],
    all_spaces: list[dict[str, Any]],
    exclusive_suspects: dict[str, Any] | None = None,
) -> str:

    # Le clip de heatmap doit utiliser EXACTEMENT la même zone isolée
    # que le dessin. Sinon deux espaces suspects pourraient encore
    # partager une partie de la surface de heatmap.
    d, _ = isolated_path_data(
        space,
        bounds,
        all_spaces,
        exclusive_suspects,
    )

    if not d:
        return ""

    raw_id = space.get("id", "")
    sid = safe_id(raw_id)

    return (
        f'<clipPath '
        f'id="clip-space-{sid}" '
        f'clipPathUnits="userSpaceOnUse" '
        f'data-space-id="{esc(raw_id)}">'
        f'<path '
        f'd="{d}" '
        f'fill-rule="evenodd" '
        f'clip-rule="evenodd" />'
        f'</clipPath>\n'
    )


def draw_room_label(
    space: dict[str, Any],
    bounds: dict[str, Any],
) -> str:

    points = get_space_points(
        space,
        bounds,
    )

    center = polygon_centroid(points)

    if center is None:
        return ""

    x, y = center

    raw_id = space.get("id", "")
    code = clean(space.get("code"))
    name = space_label(space)

    result = []

    if name:
        result.append(
            f'<text '
            f'x="{x:.3f}" '
            f'y="{y - 6:.3f}" '
            f'class="ifc-space-label" '
            f'data-space-id="{esc(raw_id)}">'
            f'{esc(name)}'
            f'</text>\n'
        )

    if code and code != name:
        result.append(
            f'<text '
            f'x="{x:.3f}" '
            f'y="{y + 9:.3f}" '
            f'class="ifc-space-code" '
            f'data-space-id="{esc(raw_id)}">'
            f'{esc(code)}'
            f'</text>\n'
        )

    return "".join(result)


# ==================================================================
# SVG : éléments IFC
# ==================================================================

def draw_element(
    element: dict[str, Any],
    bounds: dict[str, Any],
    css_class: str,
) -> str:

    result = []

    element_id = element.get("id", "")
    element_name = clean(element.get("name"))
    element_type = clean(element.get("type"))

    for line in element.get("lines") or []:

        x1, y1, x2, y2 = normalize_line(
            line,
            bounds,
        )

        result.append(
            f'<line '
            f'x1="{x1:.3f}" '
            f'y1="{y1:.3f}" '
            f'x2="{x2:.3f}" '
            f'y2="{y2:.3f}" '
            f'class="{css_class}" '
            f'data-element-id="{esc(element_id)}" '
            f'data-element-name="{esc(element_name)}" '
            f'data-layer="{esc(element_type)}" '
            f'/>\n'
        )

    return "".join(result)


# ==================================================================
# SVG complet
# ==================================================================

def build_svg(
    floor_data: dict[str, Any],
) -> tuple[str, int, int]:

    bounds = floor_data["bounds"]

    width = float(bounds["width"])
    height = float(bounds["height"])

    floor = floor_data.get("floor") or {}

    floor_id = floor.get("id", "")
    floor_name = clean(floor.get("name"))

    all_spaces = floor_data.get("spaces") or []

    rooms, containers = classify_spaces(
        all_spaces,
        bounds,
    )

    # Partition géométrique calculée une seule fois : les suspects ont des
    # surfaces exclusives et cette même partition sert au dessin ET aux clips.
    exclusive_suspects = build_exclusive_suspect_geometries(
        all_spaces,
        bounds,
    )

    elements = floor_data.get("elements") or []

    walls = [
        e for e in elements
        if e.get("type") == "wall"
    ]

    doors = [
        e for e in elements
        if e.get("type") == "door"
    ]

    windows = [
        e for e in elements
        if e.get("type") == "window"
    ]

    out = []

    out.append(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
    )

    out.append(
        f'<svg '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width:.3f} {height:.3f}" '
        f'width="{width:.3f}" '
        f'height="{height:.3f}" '
        f'data-floor-id="{esc(floor_id)}" '
        f'data-floor-name="{esc(floor_name)}" '
        f'data-coordinate-system="campus-dijon-webapp" '
        f'data-heatmap-ready="true">\n'
    )

    # --------------------------------------------------------------
    # Métadonnées
    # --------------------------------------------------------------

    out.append(
        "<metadata>\n"
        "  <campus-dijon>\n"
        "    <coordinate-system>webapp-svg</coordinate-system>\n"
        "    <origin>top-left</origin>\n"
        "    <x-axis>right</x-axis>\n"
        "    <y-axis>down</y-axis>\n"
        f"    <min-x>{bounds['min_x']}</min-x>\n"
        f"    <max-x>{bounds['max_x']}</max-x>\n"
        f"    <min-y>{bounds['min_y']}</min-y>\n"
        f"    <max-y>{bounds['max_y']}</max-y>\n"
        f"    <width>{width}</width>\n"
        f"    <height>{height}</height>\n"
        f"    <ifc-space-count>{len(all_spaces)}</ifc-space-count>\n"
        f"    <heatmap-room-count>{len(rooms)}</heatmap-room-count>\n"
        f"    <suspected-container-count>{len(containers)}</suspected-container-count>\n"
        "  </campus-dijon>\n"
        "</metadata>\n"
    )

    # --------------------------------------------------------------
    # CLIP PATHS : UNIQUEMENT les vraies zones heatmap.
    # --------------------------------------------------------------

    out.append("<defs>\n")

    for room in rooms:
        out.append(
            draw_room_clip(
                room,
                bounds,
                rooms,
                exclusive_suspects,
            )
        )

    out.append("</defs>\n")

    # --------------------------------------------------------------
    # Styles
    # --------------------------------------------------------------

    out.append(
        f"""
<style>
  .ifc-space {{
    fill: {SPACE_FILL};
    fill-opacity: .32;
    stroke: {SPACE_STROKE};
    stroke-width: 2;
    vector-effect: non-scaling-stroke;
    cursor: pointer;
  }}

  .ifc-space:hover {{
    fill-opacity: .58;
    stroke-width: 3;
  }}

  .ifc-wall {{
    fill: none;
    stroke: {WALL_STROKE};
    stroke-width: 5;
    stroke-linecap: round;
    vector-effect: non-scaling-stroke;
    pointer-events: none;
  }}

  .ifc-door {{
    fill: none;
    stroke: {DOOR_STROKE};
    stroke-width: 4;
    stroke-linecap: round;
    vector-effect: non-scaling-stroke;
    pointer-events: none;
  }}

  .ifc-window {{
    fill: none;
    stroke: {WINDOW_STROKE};
    stroke-width: 4;
    stroke-linecap: round;
    vector-effect: non-scaling-stroke;
    pointer-events: none;
  }}

  .ifc-space-label {{
    fill: {TEXT_COLOR};
    font-family: Inter, Arial, sans-serif;
    font-size: 13px;
    font-weight: 600;
    text-anchor: middle;
    dominant-baseline: middle;
    pointer-events: none;
    paint-order: stroke;
    stroke: {BG};
    stroke-width: 4;
  }}

  .ifc-space-code {{
    fill: {CODE_COLOR};
    font-family: Inter, Arial, sans-serif;
    font-size: 10px;
    font-weight: 500;
    text-anchor: middle;
    dominant-baseline: middle;
    pointer-events: none;
    paint-order: stroke;
    stroke: {BG};
    stroke-width: 3;
  }}
</style>
"""
    )

    # --------------------------------------------------------------
    # Fond
    # --------------------------------------------------------------

    out.append(
        f'<rect '
        f'x="0" y="0" '
        f'width="{width:.3f}" '
        f'height="{height:.3f}" '
        f'fill="{BG}" '
        f'data-layer="background" />\n'
    )

    # --------------------------------------------------------------
    # ZONES HEATMAP / SALLES
    #
    # Toutes les zones sont conservées. Les espaces recouvrants
    # génériques sont isolés par des sous-chemins dans leur propre
    # path lorsqu'ils englobent d'autres salles.
    # --------------------------------------------------------------

    out.append(
        '<g id="spaceGroup" data-layer="spaces">\n'
    )

    for room in rooms:
        out.append(
            draw_room(
                room,
                bounds,
                all_spaces,
                exclusive_suspects,
            )
        )

    out.append("</g>\n")

    # --------------------------------------------------------------
    # HEATMAP
    #
    # Ce groupe est volontairement AU-DESSUS des salles et séparé
    # de leur géométrie.
    # --------------------------------------------------------------

    out.append(
        '<g id="heatmapGroup" '
        'data-layer="heatmap" '
        'pointer-events="none">\n'
        '</g>\n'
    )

    # --------------------------------------------------------------
    # MURS
    # --------------------------------------------------------------

    out.append(
        '<g id="wallGroup" data-layer="walls">\n'
    )

    for wall in walls:
        out.append(
            draw_element(
                wall,
                bounds,
                "ifc-wall",
            )
        )

    out.append("</g>\n")

    # --------------------------------------------------------------
    # PORTES
    # --------------------------------------------------------------

    out.append(
        '<g id="doorGroup" data-layer="doors">\n'
    )

    for door in doors:
        out.append(
            draw_element(
                door,
                bounds,
                "ifc-door",
            )
        )

    out.append("</g>\n")

    # --------------------------------------------------------------
    # FENETRES
    # --------------------------------------------------------------

    out.append(
        '<g id="windowGroup" data-layer="windows">\n'
    )

    for window in windows:
        out.append(
            draw_element(
                window,
                bounds,
                "ifc-window",
            )
        )

    out.append("</g>\n")

    # --------------------------------------------------------------
    # LABELS
    # --------------------------------------------------------------

    out.append(
        '<g id="labelGroup" data-layer="labels">\n'
    )

    for room in rooms:
        out.append(
            draw_room_label(
                room,
                bounds,
            )
        )

    out.append("</g>\n")

    # --------------------------------------------------------------
    # Les espaces suspects sont conservés dans la couche principale.
    # Ils restent sélectionnables : ce sont peut-être de vraies salles.
    # On les expose seulement via data-suspected-container="true".
    # --------------------------------------------------------------

    out.append("</svg>\n")

    return (
        "".join(out),
        len(rooms),
        len(containers),
    )


# ==================================================================
# Export
# ==================================================================

def export_floor(
    floor_name: str,
    output_dir: Path,
) -> Path:

    floor_data = get_floor_geometry(
        floor_name
    )

    if not floor_data.get("bounds"):
        raise RuntimeError(
            f"Aucune géométrie exploitable pour {floor_name}"
        )

    svg, room_count, container_count = build_svg(
        floor_data
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / f"{floor_name}.svg"
    )

    output_path.write_text(
        svg,
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print(f"Étage : {floor_name}")
    print("=" * 60)
    print(
        f"IfcSpace détectés : "
        f"{len(floor_data.get('spaces') or [])}"
    )
    print(
        f"Zones heatmap     : {room_count}"
    )
    print(
        f"Espaces suspects (conservés): {container_count}"
    )
    print(
        f"SVG               : {output_path}"
    )

    return output_path


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Exporte les étages IFC en SVG, "
            "avec une vraie zone indépendante par salle."
        )
    )

    parser.add_argument(
        "--floor",
        help="Exporter uniquement un étage, ex. N1",
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Dossier de sortie (défaut : {DEFAULT_OUTPUT})",
    )

    args = parser.parse_args()

    output_dir = Path(args.output)

    if args.floor:

        export_floor(
            args.floor,
            output_dir,
        )

        return

    floors = [
        floor
        for floor in get_floors()
        if floor.get("name") not in EXCLUDED_FLOORS
    ]

    if not floors:
        raise RuntimeError(
            "Aucun étage IFC trouvé."
        )

    for floor in floors:

        floor_name = floor.get("name")

        if not floor_name:
            continue

        try:

            export_floor(
                floor_name,
                output_dir,
            )

        except Exception as error:

            print(
                f"[ERREUR] {floor_name}: {error}"
            )


if __name__ == "__main__":
    main()
