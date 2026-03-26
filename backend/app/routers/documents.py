from fastapi import APIRouter, HTTPException, Depends
from typing import Any
import uuid
import logging

from app.config import settings
from app.models.schemas import DocumentRequest, DocumentResponse
from app.dependencies import (
    ChromaServiceDep,
    DataServiceDep,
    verify_api_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, dependencies=[Depends(verify_api_key)])
async def add_document(
    request: DocumentRequest,
    chroma: ChromaServiceDep,
) -> DocumentResponse:
    """Добавить документ в Chroma."""
    doc_id = str(uuid.uuid4())

    try:
        chroma.add_documents(
            texts=[request.text],
            metadatas=[{"source": request.source, **request.metadata}],
            ids=[doc_id],
        )
        
        return DocumentResponse(
            id=doc_id,
            text=request.text,
            source=request.source,
            metadata=request.metadata,
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении документа: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при добавлении документа. Проверьте логи.")


@router.get("", response_model=list[DocumentResponse], dependencies=[Depends(verify_api_key)])
async def list_documents(
    chroma: ChromaServiceDep,
    source: str | None = None,
) -> list[DocumentResponse]:
    """Получить список всех документов из Chroma."""
    try:
        results = chroma.search("", n_results=100)
        
        documents = []
        for doc in results:
            if source is None or doc["metadata"].get("source") == source:
                documents.append(DocumentResponse(
                    id=doc["id"],
                    text=doc["text"],
                    source=doc["metadata"].get("source", ""),
                    metadata=doc["metadata"],
                ))
        
        return documents
    except Exception as e:
        logger.error(f"Ошибка при получении списка документов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении документов. Проверьте логи.")


@router.delete("/{doc_id}", dependencies=[Depends(verify_api_key)])
async def delete_document(
    doc_id: str,
    chroma: ChromaServiceDep,
) -> dict:
    """Удалить документ из Chroma."""
    try:
        deleted = chroma.delete_document(doc_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Документ {doc_id} не найден")
        return {"status": "deleted", "id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при удалении документа {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при удалении документа. Проверьте логи.")


async def reindex_chroma(chroma, data, clear: bool = False) -> dict[str, Any]:
    """Переиспользуемая функция индексации данных в ChromaDB для RAG.

    Вызывается из API-эндпоинта и из scheduler после сбора данных.
    """
    if clear:
        chroma.clear_collection()

    texts: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    errors: list[str] = []

    try:
        hotels, _ = await data.get_hotels(limit=500)
        for hotel in hotels:
            texts.append(_format_hotel_text(hotel))
            metadatas.append({
                "source": "pg_hotels",
                "hotel_id": hotel.id,
                "city": hotel.city or "",
                "district": hotel.district or "",
                "type": "hotel",
            })
            ids.append(f"hotel_{hotel.id}")
    except Exception as e:
        errors.append(f"Hotels fetch: {str(e)}")

    try:
        events_data = await data.get_events()
        for event in events_data:
            texts.append(_format_event_text(event))
            event_id = event.get("event_id", str(uuid.uuid4()))

            date_start = event.get("date_start")
            date_epoch_days = 0
            date_str = ""
            if date_start:
                from datetime import datetime, timedelta
                if isinstance(date_start, int):
                    date_epoch_days = date_start
                    date_obj = datetime(1970, 1, 1) + timedelta(days=date_start)
                    date_str = date_obj.strftime("%Y-%m-%d")
                else:
                    try:
                        date_obj = datetime.fromisoformat(str(date_start)[:10])
                        date_epoch_days = (date_obj - datetime(1970, 1, 1)).days
                        date_str = date_obj.strftime("%Y-%m-%d")
                    except ValueError:
                        date_str = str(date_start)[:10]

            metadatas.append({
                "source": "pg_events",
                "event_id": event_id,
                "type": "event",
                "date_epoch_days": date_epoch_days,
                "date_start": date_str,
                "event_type": _map_event_type(event.get("event_type", "")),
            })
            ids.append(f"event_{event_id}")
    except Exception as e:
        errors.append(f"Events fetch: {str(e)}")

    indexed_count = 0
    if texts:
        try:
            indexed_count = chroma.add_documents_batch(
                texts=texts,
                metadatas=metadatas,
                ids=ids,
                batch_size=settings.rag_index_batch_size,
            )
        except Exception as e:
            errors.append(f"Indexing: {str(e)}")

    return {
        "status": "ok",
        "indexed_count": indexed_count,
        "total_documents": len(texts),
        "collection_count": chroma.get_collection_count(),
        "errors": errors[:10] if errors else [],
    }


@router.post("/reindex", dependencies=[Depends(verify_api_key)])
async def index_data(
    chroma: ChromaServiceDep,
    data: DataServiceDep,
    clear: bool = False,
) -> dict[str, Any]:
    """Индексировать отели и события из БД в ChromaDB для RAG."""
    return await reindex_chroma(chroma, data, clear=clear)


@router.get("/stats", dependencies=[Depends(verify_api_key)])
async def get_stats(chroma: ChromaServiceDep) -> dict[str, Any]:
    """Получить статистику коллекции."""
    return {
        "collection_count": chroma.get_collection_count(),
    }


def _format_hotel_text(hotel) -> str:
    """Форматировать информацию об отеле для индексации."""
    parts = [f"Отель {hotel.name}"]
    
    if hotel.city:
        parts.append(f"в городе {hotel.city}")
    
    if hotel.district:
        parts.append(f"({hotel.district} район)")
    
    if hotel.rating:
        parts.append(f"Рейтинг: {hotel.rating}")
    
    min_price = getattr(hotel, 'min_price', None)
    if min_price:
        parts.append(f"Минимальная цена: {min_price} руб.")
    
    return ". ".join(parts) + "."


def _map_event_type(event_type: str) -> str:
    """Маппинг типов мероприятий в читаемые названия."""
    type_mapping = {
        "другой": "культурное мероприятие",
        "other": "культурное мероприятие",
        "concert": "концерт",
        "концерт": "концерт",
        "theatre": "театр",
        "спектакль": "театр",
        "exhibition": "выставка",
        "выставка": "выставка",
        "festival": "фестиваль",
        "фестиваль": "фестиваль",
        "conference": "конференция",
        "конференция": "конференция",
        "бизнес-событие": "бизнес-событие",
        "business": "бизнес-событие",
        "sport": "спортивное событие",
        "спорт": "спортивное событие",
        "holiday": "праздник",
        "праздник": "праздник",
        "tourism": "туристическое событие",
    }
    if not event_type:
        return "событие"
    return type_mapping.get(event_type.lower(), event_type)


def _format_event_text(event: dict) -> str:
    """Форматировать информацию о событии для индексации."""
    from datetime import datetime, timedelta
    
    title = event.get("title", "Событие")
    parts = [title]
    
    location = event.get("location", "")
    if location:
        parts.append(f"Место: {location}")
    
    date_start = event.get("date_start")
    if date_start:
        # Конвертация epoch days (int) в читаемую дату
        if isinstance(date_start, int):
            date_obj = datetime(1970, 1, 1) + timedelta(days=date_start)
            date_str = date_obj.strftime("%d.%m.%Y")
        else:
            date_str = str(date_start)
        parts.append(f"Дата: {date_str}")
    
    event_type = event.get("event_type", "")
    if event_type:
        readable_type = _map_event_type(event_type)
        parts.append(f"Тип: {readable_type}")
    
    return ". ".join(parts) + "."
