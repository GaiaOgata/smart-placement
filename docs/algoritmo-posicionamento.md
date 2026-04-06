# Algoritmo de Posicionamento — Fuga dos Pontos de Calor

## Visão Geral

O sistema adota uma abordagem de **otimização por busca global**: para cada objeto (overlay), todos os posicionamentos válidos são avaliados simultaneamente e o de menor custo total é escolhido.

O custo total combina dois critérios:
- **Calor acumulado** — evitar regiões quentes do heatmap
- **Distância à posição original** — penalizar deslocamentos grandes *(novo)*

---

## Pipeline Completo

```
Imagem do heatmap (RGB)
        │
        ▼
[ 1. rgb_to_intensity ]  →  Matriz de intensidade float32 (H × W)
        │
        ▼
[ 2. find_optimal_position ]
        ├─ FFT convolution  →  heat_map (custo de calor por posição)
        ├─ Distance map     →  dist_map (distância à origem por posição)  
        ├─ Normalização + ponderação  →  total_cost = (1-w)·heat + w·dist  
        └─ argmin(total_cost)  →  (x, y) ótimo
        │
        ▼
  Objeto reposicionado
```

---

## Etapa 1 — Conversão do Heatmap em Intensidade

**Arquivo:** `app/services/heatmap.py`
**Função:** `rgb_to_intensity(image) -> np.ndarray`

Transforma a imagem RGB em uma matriz numérica 2D onde cada pixel vale entre `0.0` (frio/azul) e `1.0` (quente/vermelho).

### Fórmula de intensidade

```
hue_degrees = hue_raw × (360 / 255)
intensity   = 1.0 − (hue_degrees / 240.0)  →  clampado em [0.0, 1.0]
```

Pixels transparentes, escuros ou acromáticos são zerados.

---

## Etapa 2 — Busca da Posição Ótima

**Arquivo:** `app/services/placement.py`
**Função:** `find_optimal_position(intensity, overlay_width, overlay_height, origin_x, origin_y, distance_weight)`

### Parâmetros novos

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `origin_x` | int | `0` | Coluna do canto superior esquerdo da posição original |
| `origin_y` | int | `0` | Linha do canto superior esquerdo da posição original |
| `distance_weight` | float [0–1] | `0.3` | Peso da penalidade de distância |

### Passo a passo

**1. Mapa de calor via convolução FFT**
```python
kernel   = np.ones((overlay_height, overlay_width))
heat_map = fftconvolve(intensity, kernel, mode="valid")
```
Cada célula `heat_map[r, c]` = soma de calor coberta pelo objeto se posicionado em `(c, r)`.

**2. Mapa de distâncias** *(novo)*
```python
dist_map[r, c] = sqrt((c - origin_x)² + (r - origin_y)²)
```
Cada célula é a distância euclidiana até a posição original do objeto.

**3. Normalização de ambos para [0, 1]** *(novo)*
```python
norm_heat = heat_map / heat_map.max()
norm_dist = dist_map / dist_map.max()
```
A normalização coloca os dois critérios na mesma escala antes de combiná-los.

**4. Custo total ponderado** *(novo)*
```python
total_cost = (1 - distance_weight) * norm_heat + distance_weight * norm_dist
```

**5. Posição ótima**
```python
argmin(total_cost)  →  (min_x, min_y)
```

### Efeito do `distance_weight`

| Valor | Comportamento |
|-------|---------------|
| `0.0` | Comportamento original: ignora distância, vai para a região mais fria possível |
| `0.3` | **Padrão atual:** prefere regiões frias, mas penaliza deslocamentos grandes |
| `0.5` | Equilíbrio entre fugir do calor e ficar próximo |
| `1.0` | Fica exatamente na posição original, ignorando o calor |

---

## Parâmetro via API

**Endpoint:** `POST /api/optimize`

O `distance_weight` pode ser enviado no `form-data`:

```
distance_weight=0.3   ← valor padrão se omitido
```

**Exemplo de resposta:**
```json
{
  "id": "objeto-1",
  "original":  { "x": 320, "y": 150 },
  "optimized": { "x": 180, "y": 210 },
  "original_heat_sum":  0.87,
  "optimized_heat_sum": 0.15
}
```

Com `distance_weight > 0`, o objeto tende a se mover menos do que antes — o deslocamento `original → optimized` será moderado em vez de ir para o canto mais frio da imagem.

---

## Diagrama Visual do Custo Total

```
Sem penalidade (w=0)          Com penalidade (w=0.3)
┌─────────────────────┐       ┌─────────────────────┐
│  🔵🔵🔵🔵🔵🔵🔵🔵  │       │  🟢🔵🔵🔵🔵🔵🔵🔵  │
│  🔵🔵🔵🔵🔵🔵🔵🔵  │       │  🟢🟢🔵🔵🔵🔵🔵🔵  │
│  🔵🔵🔴🔴🔴🔵🔵🔵  │       │  🟢🟢🟡🔴🔴🔵🔵🔵  │
│  🔵🔵🔴🔴🔴🔵🔵🔵  │       │  🟢🟢🟡🔴🔴🔵🔵🔵  │
│  🔵🔵🔵🔵🔵🔵🔵🔵  │  →   │  🟢🟡🟡🔵🔵🔵🔵🔵  │
│  🔵🔵🔵🔵🔵🔵🔵🔵  │       │  🟡🟡🟡🔵🔵🔵🔵🔵  │
│  🔵🔵🔵🔵🔵🔵🔵⭐  │       │  🟡🟡🟡🔵🔵🔵🔵⭐  │  ← origem
└─────────────────────┘       └─────────────────────┘
  Objeto vai para qualquer        Objeto prefere ficar
  canto frio (⭐ = eleito)        próximo da origem (⭐)

🔴 = muito quente  🟡 = custo moderado (distância)  🔵 = frio  🟢 = frio + próximo
```

---

## Limitações

1. **Objetos não interagem entre si** — cada objeto é posicionado de forma independente, sem considerar sobreposição com outros.
2. **Distância euclidiana simples** — não considera obstáculos ou restrições de layout.
3. **`distance_weight` único para todos os overlays** — não é possível configurar por objeto individualmente.
