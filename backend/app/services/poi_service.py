"""POI-сервис: достопримечательности и точки интереса через OpenStreetMap Overpass API."""
import asyncio
import aiohttp
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

OVERPASS_API = "https://overpass-api.de/api/interpreter"

BAIKAL_BBOX = "51.5,103.5,53.5,108.0"

POI_CATEGORIES = {
    "tourism": {
        "tags": '["tourism"~"attraction|museum|viewpoint|information|artwork"]',
        "label": "Достопримечательности",
    },
    "nature": {
        "tags": '["natural"~"peak|beach|hot_spring|spring|cave_entrance|glacier"]',
        "label": "Природа",
    },
    "culture": {
        "tags": '["amenity"~"theatre|cinema|arts_centre|library"]',
        "label": "Культура",
    },
    "transport": {
        "tags": '["aeroway"="aerodrome"]["iata"]',
        "label": "Аэропорты",
    },
    "bus_station": {
        "tags": '["amenity"="bus_station"]',
        "label": "Автовокзалы",
    },
    "train": {
        "tags": '["railway"="station"]["train"="yes"]',
        "label": "Ж/д станции",
    },
}


_CACHE_TTL = 3600
_MAX_CACHE_SIZE = 30


class POIService:
    """Сервис для получения POI из OpenStreetMap."""

    def __init__(self):
        self._cache: dict[str, dict] = {}  # {key: {"data": ..., "ts": ...}}

    async def get_pois(
        self,
        category: str = "tourism",
        bbox: str = BAIKAL_BBOX,
        limit: int = 50,
    ) -> list[dict]:
        """Получить POI по категории.

        Args:
            category: Ключ из POI_CATEGORIES
            bbox: Bounding box "south,west,north,east"
            limit: Максимум результатов
        """
        cache_key = f"{category}:{bbox}"
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if time.time() - entry["ts"] < _CACHE_TTL:
                return entry["data"][:limit]
            del self._cache[cache_key]

        cat = POI_CATEGORIES.get(category)
        if not cat:
            return []

        query = f"""
        [out:json][timeout:25];
        (
          node{cat['tags']}({bbox});
          way{cat['tags']}({bbox});
        );
        out center {limit};
        """

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    OVERPASS_API,
                    data={"data": query},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Overpass API: {response.status}")
                        return []
                    data = await response.json()
        except Exception as e:
            logger.error(f"POI fetch error: {e}")
            return []

        results = []
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:ru") or tags.get("name:en")
            if not name:
                continue

            lat = el.get("lat") or (el.get("center", {}).get("lat"))
            lon = el.get("lon") or (el.get("center", {}).get("lon"))
            if not lat or not lon:
                continue

            results.append({
                "name": name,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "category": category,
                "category_label": cat["label"],
                "type": tags.get("tourism") or tags.get("natural") or tags.get("amenity") or tags.get("railway") or "",
                "description": tags.get("description") or tags.get("description:ru") or "",
                "wikipedia": tags.get("wikipedia") or "",
                "website": tags.get("website") or tags.get("url") or "",
            })

        if len(self._cache) >= _MAX_CACHE_SIZE:
            oldest_key = min(self._cache, key=lambda k: self._cache[k]["ts"])
            del self._cache[oldest_key]
        self._cache[cache_key] = {"data": results, "ts": time.time()}
        return results[:limit]

    async def get_all_categories(self, limit_per_category: int = 20) -> dict[str, list[dict]]:
        """Получить POI по всем категориям."""
        results = await asyncio.gather(
            *[self.get_pois(category=cat, limit=limit_per_category) for cat in POI_CATEGORIES],
            return_exceptions=True,
        )
        return {
            cat: pois for cat, pois in zip(POI_CATEGORIES, results)
            if isinstance(pois, list) and pois
        }


    async def get_pois_with_fallback(
        self,
        category: str = "tourism",
        limit: int = 30,
    ) -> list[dict]:
        """POI с fallback-описаниями для пустых description."""
        result = await self.get_pois(category=category, limit=limit)
        if not result:
            return _FALLBACK_POIS.get(category, [])[:limit]

        fallback = _FALLBACK_POIS.get(category, [])
        desc_map = {fb["name"].lower(): fb.get("description", "") for fb in fallback}
        for poi in result:
            if poi.get("description"):
                continue
            name_lower = poi["name"].lower()
            if name_lower in desc_map:
                poi["description"] = desc_map[name_lower]
                continue
            for fb_name, fb_desc in desc_map.items():
                if fb_name in name_lower or name_lower in fb_name:
                    poi["description"] = fb_desc
                    break
            else:
                poi["description"] = _TYPE_DESCRIPTIONS.get(poi.get("type", ""), "")
        return result


_TYPE_DESCRIPTIONS: dict[str, str] = {
    "museum": "Музей",
    "viewpoint": "Смотровая площадка",
    "attraction": "Достопримечательность",
    "information": "Туристический информационный пункт",
    "artwork": "Арт-объект",
    "peak": "Горная вершина",
    "beach": "Пляж",
    "hot_spring": "Горячий источник",
    "spring": "Природный источник",
    "cave_entrance": "Вход в пещеру",
    "glacier": "Ледник",
    "lake": "Озеро",
    "island": "Остров",
    "river": "Река",
    "strait": "Пролив",
    "theatre": "Театр",
    "cinema": "Кинотеатр",
    "arts_centre": "Культурный центр",
    "library": "Библиотека",
    "aerodrome": "Аэропорт",
    "bus_station": "Автовокзал",
    "station": "Железнодорожная станция",
}

_FALLBACK_POIS: dict[str, list[dict]] = {
    "tourism": [
        {"name": "Байкальский музей", "lat": 51.862, "lon": 104.856, "category": "tourism", "category_label": "Достопримечательности", "type": "museum", "description": "Экспозиция о Байкале, аквариумы с нерпами", "wikipedia": "", "website": "https://bm.isc.irk.ru"},
        {"name": "Камень Черского", "lat": 51.857, "lon": 104.848, "category": "tourism", "category_label": "Достопримечательности", "type": "viewpoint", "description": "Смотровая площадка с видом на исток Ангары", "wikipedia": "", "website": ""},
        {"name": "Нерпинарий", "lat": 51.861, "lon": 104.852, "category": "tourism", "category_label": "Достопримечательности", "type": "attraction", "description": "Шоу байкальских нерп", "wikipedia": "", "website": ""},
        {"name": "Шаман-скала (Бурхан)", "lat": 53.205, "lon": 107.345, "category": "tourism", "category_label": "Достопримечательности", "type": "attraction", "description": "Священное место на острове Ольхон", "wikipedia": "ru:Скала Шаманка", "website": ""},
        {"name": "Тальцы", "lat": 51.978, "lon": 104.624, "category": "tourism", "category_label": "Достопримечательности", "type": "museum", "description": "Архитектурно-этнографический музей под открытым небом", "wikipedia": "ru:Тальцы (музей)", "website": "https://talfreak.ru"},
        {"name": "130-й квартал", "lat": 52.280, "lon": 104.285, "category": "tourism", "category_label": "Достопримечательности", "type": "attraction", "description": "Исторический квартал с деревянной архитектурой в Иркутске", "wikipedia": "", "website": ""},
        {"name": "КБЖД (Кругобайкальская железная дорога)", "lat": 51.730, "lon": 104.040, "category": "tourism", "category_label": "Достопримечательности", "type": "attraction", "description": "Историческая железная дорога вдоль южного берега Байкала", "wikipedia": "ru:Кругобайкальская железная дорога", "website": ""},
        {"name": "Мыс Хобой", "lat": 53.410, "lon": 107.790, "category": "tourism", "category_label": "Достопримечательности", "type": "viewpoint", "description": "Северная оконечность Ольхона, панорамный вид", "wikipedia": "", "website": ""},
        {"name": "Песчаная бухта", "lat": 52.270, "lon": 105.730, "category": "tourism", "category_label": "Достопримечательности", "type": "attraction", "description": "Живописная бухта с ходульными деревьями", "wikipedia": "", "website": ""},
        {"name": "Пик Черского", "lat": 51.517, "lon": 103.650, "category": "tourism", "category_label": "Достопримечательности", "type": "viewpoint", "description": "Высшая точка хребта Хамар-Дабан, 2090 м", "wikipedia": "", "website": ""},
    ],
    "nature": [
        {"name": "Озеро Байкал", "lat": 53.5, "lon": 108.0, "category": "nature", "category_label": "Природа", "type": "lake", "description": "Самое глубокое озеро мира, объект ЮНЕСКО", "wikipedia": "ru:Байкал", "website": ""},
        {"name": "Остров Ольхон", "lat": 53.15, "lon": 107.38, "category": "nature", "category_label": "Природа", "type": "island", "description": "Крупнейший остров Байкала", "wikipedia": "ru:Ольхон", "website": ""},
        {"name": "Аршан (минеральные источники)", "lat": 51.91, "lon": 102.43, "category": "nature", "category_label": "Природа", "type": "hot_spring", "description": "Курорт с минеральными водами в Тункинской долине", "wikipedia": "", "website": ""},
        {"name": "Пролив Малое Море", "lat": 53.0, "lon": 106.8, "category": "nature", "category_label": "Природа", "type": "strait", "description": "Пролив между Ольхоном и материком", "wikipedia": "", "website": ""},
        {"name": "Ангара (исток)", "lat": 51.87, "lon": 104.83, "category": "nature", "category_label": "Природа", "type": "river", "description": "Единственная река, вытекающая из Байкала", "wikipedia": "ru:Ангара", "website": ""},
    ],
    "culture": [
        {"name": "Иркутский драматический театр", "lat": 52.284, "lon": 104.281, "category": "culture", "category_label": "Культура", "type": "theatre", "description": "Старейший драматический театр Восточной Сибири (1850)", "wikipedia": "", "website": ""},
        {"name": "Иркутский музыкальный театр", "lat": 52.291, "lon": 104.296, "category": "culture", "category_label": "Культура", "type": "theatre", "description": "Театр музыкальной комедии", "wikipedia": "", "website": ""},
        {"name": "Иркутский областной краеведческий музей", "lat": 52.285, "lon": 104.280, "category": "culture", "category_label": "Культура", "type": "arts_centre", "description": "Крупнейший музей Восточной Сибири, основан в 1782", "wikipedia": "", "website": ""},
        {"name": "Галерея Виктора Бронштейна", "lat": 52.281, "lon": 104.286, "category": "culture", "category_label": "Культура", "type": "arts_centre", "description": "Частная галерея современного искусства", "wikipedia": "", "website": ""},
    ],
    "transport": [
        {"name": "Аэропорт Иркутск", "lat": 52.268, "lon": 104.389, "category": "transport", "category_label": "Аэропорты", "type": "aerodrome", "description": "Международный аэропорт (IKT), главный хаб региона", "wikipedia": "", "website": ""},
    ],
}


poi_service = POIService()
