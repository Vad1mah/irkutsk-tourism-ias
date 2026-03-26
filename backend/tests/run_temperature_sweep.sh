#!/bin/bash
# Массовое тестирование LLM на разных температурах

cd /Users/vad1mah/Downloads/Diplom/backend
source venv/bin/activate

TEMPERATURES=(0.1 0.2 0.3 0.5 0.7)
RESULTS_DIR="tests/temperature_results"
mkdir -p "$RESULTS_DIR"

echo "======================================"
echo "TEMPERATURE SWEEP TEST"
echo "======================================"

for TEMP in "${TEMPERATURES[@]}"; do
    echo ""
    echo ">>> Тестирование температуры: $TEMP"
    
    # Меняем температуру в .env
    sed -i.bak "s/GIGACHAT_TEMPERATURE=.*/GIGACHAT_TEMPERATURE=$TEMP/" .env
    
    # Убиваем старый сервер
    pkill -f "uvicorn.*8000" 2>/dev/null
    sleep 2
    
    # Запускаем новый
    uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    SERVER_PID=$!
    sleep 8
    
    # Проверяем что сервер запустился
    if ! curl -s http://localhost:8000/api/query/llm-info > /dev/null; then
        echo "❌ Сервер не запустился для temp=$TEMP"
        continue
    fi
    
    # Запускаем тесты
    python tests/test_llm_temperatures.py 2>&1 | tee "$RESULTS_DIR/temp_${TEMP}.log"
    
    # Копируем JSON результаты
    mv tests/results_*.json "$RESULTS_DIR/results_temp_${TEMP}.json" 2>/dev/null
    
    echo ">>> Завершено для temp=$TEMP"
done

# Восстанавливаем оригинальную температуру
sed -i.bak "s/GIGACHAT_TEMPERATURE=.*/GIGACHAT_TEMPERATURE=0.2/" .env

echo ""
echo "======================================"
echo "ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ"
echo "Результаты в: $RESULTS_DIR"
echo "======================================"
