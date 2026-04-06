# API de Otimização de Posicionamento sobre Mapa de Calor

## Contexto
API que recebe um mapa de calor (imagem RGB) e 1-10 imagens overlay com coordenadas x,y. O algoritmo encontra posições ótimas para cada overlay, minimizando a sobreposição com áreas "quentes" do mapa. Retorna as novas coordenadas otimizadas em JSON.

## Stack
- Python + Flask
- Pillow (imagens), NumPy (matrizes), SciPy (convolução FFT)
- ngrok para expor URL público (integração com n8n)

## Estrutura do Projeto
```
image-analysis/
├── app/
│   ├── __init__.py          # App factory Flask
│   ├── config.py            # Configurações (max file size, etc.)
│   ├── routes/
│   │   ├── __init__.py
│   │   └── optimize.py      # POST /api/optimize
│   ├── services/
│   │   ├── __init__.py
│   │   ├── heatmap.py       # Conversão RGB → matriz de intensidade
│   │   └── placement.py     # Algoritmo de posicionamento (convolução FFT)
│   └── utils/
│       ├── __init__.py
│       └── image_utils.py   # Helpers de imagem
├── tests/
│   ├── test_heatmap.py
│   ├── test_placement.py
│   └── test_api.py
├── requirements.txt
└── run.py                   # Entry point
```

## API Endpoint

**POST /api/optimize** (`multipart/form-data`)

Request:
- `heatmap`: arquivo de imagem (PNG/JPG) — o mapa de calor
- `overlays`: 1-10 arquivos de imagem
- `metadata`: string JSON com coordenadas por overlay:
  ```json
  [{"id": "img1", "x": 100, "y": 200}, {"id": "img2", "x": 300, "y": 50}]
  ```

Response (JSON):
```json
{
  "results": [
    {
      "id": "img1",
      "original": {"x": 100, "y": 200},
      "optimized": {"x": 42, "y": 315},
      "original_heat_sum": 185432.0,
      "optimized_heat_sum": 2104.0
    }
  ]
}
```

## Algoritmo

### 1. Conversão do mapa de calor (heatmap.py)
- Converter RGB → HSV (usando Pillow)
- Extrair canal Hue: azul (frio) ≈ 240°, vermelho (quente) ≈ 0°
- Normalizar: `intensity = 1.0 - (hue / 240.0)`, clamp [0, 1]
- Resultado: matriz float32 (H × W) com 0=frio, 1=quente
- Pixels pretos/brancos/transparentes → intensidade 0

### 2. Posicionamento ótimo (placement.py)
- Como overlays podem se sobrepor entre si, cada um é otimizado **independentemente**
- Para cada overlay de tamanho (oh, ow):
  1. Criar kernel de 1s com shape (oh, ow)
  2. `cost_map = scipy.signal.fftconvolve(intensity, kernel, mode='valid')`
  3. `(min_y, min_x) = np.unravel_index(np.argmin(cost_map), cost_map.shape)`
- Complexidade: O(H × W × log(H×W)) por overlay — muito eficiente

## Passos de Implementação

1. **Scaffold**: Criar estrutura de diretórios, `requirements.txt`, `run.py`, app factory
2. **heatmap.py**: `rgb_to_intensity(image) → np.ndarray` — conversão HSV
3. **placement.py**: `find_optimal_position(intensity, w, h) → (x, y, heat_sum)` — convolução FFT
4. **optimize.py**: Endpoint Flask — parse multipart, validação, chamar services, retornar JSON
5. **app/__init__.py**: Wiring — blueprints, config, error handlers
6. **Testes**: Unitários para heatmap/placement + integração para a API
7. **Edge cases**: Overlay maior que mapa (erro 422), mapa uniforme, imagens RGBA
8. **Exposição pública**: Configurar ngrok para expor a API local com URL público acessível pelo n8n

## Dependências (requirements.txt)
```
flask>=3.0
pillow>=10.0
numpy>=1.24
scipy>=1.11
pytest>=7.0
```

## Exposição Pública (ngrok)
- Rodar Flask na porta 5000: `python run.py`
- Expor com ngrok: `ngrok http 5000`
- O ngrok gera uma URL pública (ex: `https://abc123.ngrok-free.app`) que pode ser usada no n8n como HTTP Request node apontando para `https://abc123.ngrok-free.app/api/optimize`

## Verificação
1. Rodar `pytest` para testes unitários e de integração
2. Testar manualmente com `curl` enviando um heatmap PNG e overlays
3. Validar que posições otimizadas têm `heat_sum` menor que as originais
4. Testar via ngrok URL para confirmar acesso externo (simular chamada do n8n)
