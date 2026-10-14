"""The 15 places of the map scope A/B (db/checks/validator_scope_ab.py) plus Géant and Carrefour, as the admin set them on 2026-10-14.

Names, categories and sites are those of the real places (or of the A/B fixtures). Scope is decided in code only
(agents/map_scope.py): OUT must be excluded with no model call, IN must never be excluded.
"""

OUT_OF_SCOPE = [
    {"name": "Géant Fresh Market", "category": "shop"},
    {"name": "Tienda Inglesa", "category": "shop", "website": "http://www.tiendainglesa.com.uy/"},
    {"name": "Carrefour Market", "category": "shop", "website": "https://www.carrefour.com.ar/"},
    {"name": "Devoto Express", "category": "shop"},
    {"name": "Autoservicio El Trébol", "category": "shop"},  # independent, only a gluten-free shelf
]

IN_SCOPE = [
    {"name": "Minimarket La Isla 24 hours.", "category": "shop", "website": "https://www.laisla247.com/"},
    {"name": "EntreSano Healthy Supermarket", "category": "shop", "website": "https://entresano.com/"},
    {"name": "La Molienda - Carrasco", "category": "shop", "website": "https://www.lamolienda.uy/tiendas"},
    {"name": "Zero Helados", "category": "cafe"},
    {"name": "Ramona", "category": "cafe"},
    {"name": "Mi Cocina Sin Gluten", "category": "shop"},
    {"name": "Dietética Vida Sana", "category": "shop"},                 # dietética
    {"name": "Panadería La Espiga", "category": "cafe"},                 # 100% gluten-free bakery
    {"name": "Pastas Don Luis", "category": "shop"},                     # factory with direct sale
    {"name": "La Parrilla de Juan", "category": "restaurant"},           # restaurant with options, shared grill
    {"name": "Almacén Natural Don Pepe", "category": "shop"},            # natural food shop
    {"name": "Sin Trigo Panadería", "category": "cafe"},                 # bakery that also runs workshops
]


def label(place: dict) -> str:
    return place["name"]
