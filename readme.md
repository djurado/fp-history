# 📊 FP History Dashboard

Aplicación interactiva desarrollada con **Streamlit** para el análisis académico de desempeño estudiantil por semestre, carrera y componentes evaluativos.

Este proyecto permite validar, consolidar y analizar datos históricos, proporcionando visualizaciones claras y métricas clave para la toma de decisiones académicas.

---

## 🚀 Origen del proyecto

Este proyecto es una evolución del sistema original:

👉 https://github.com/rbonillaa/FP-Dashboard.git

Se ha extendido con:

- Análisis histórico  
- Consolidación automática de datasets  
- Validación robusta basada en metadata  
- Dashboards flexibles según los datos  

---

## 🎯 Objetivos

Proveer una herramienta que permita:

- Analizar el rendimiento académico por semestre  
- Identificar tendencias históricas  
- Evaluar componentes teóricos y prácticos  
- Detectar patrones de aprobación/reprobación  
- Facilitar la toma de decisiones académicas  

---

## 🧩 Funcionalidades principales

### 📥 1. Carga y validación de datos
- Validación automática basada en metadata por semestre  
- Detección de errores estructurales y de contenido  
- Normalización de datos  

---

### 📊 2. Consolidación de datasets
- Generación de datasets por semestre  
- Unificación de múltiples archivos  
- Estructura consistente para análisis  

---

### 📈 3. Resumen general
- Indicadores clave:
  - Estudiantes  
  - Paralelos  
  - Carreras  
  - % de aprobados  
- Distribución por estado (AP, RP, RT, PF)  
- Análisis por carrera  

---

### 📉 4. Análisis histórico
- Tendencia de estados por semestre  
- Evolución del porcentaje de aprobados  
- Filtros por:
  - Facultad  
  - Carrera  
  - Veces tomada  
- Visualización en barras apiladas  

---

### 🔍 5. Detalle por semestre
- Métricas clave del semestre  
- Componentes:
  - Teóricos (parcial, final, mejoramiento)  
  - Prácticos (talleres, participación, práctico)  
- Promedios solo para estudiantes que rindieron examen  
- Análisis por temas con normalización por metadata  

---

### 🧠 6. Validación de datos
- Uso de metadata por semestre  
- Reglas dinámicas  
- Manejo robusto de errores  

---

## 🏗️ Estructura del proyecto
```
fp-history/
│
├── pages/
│   ├── 1_Resumen_general.py
│   ├── 2_Analisis_historico.py
│   └── 3_Detalle_semestre.py
├── datasets/          # NO versionado
├── metadata/          # NO versionado
├── src/
│   ├── transform/
│   │   └──consolidator_service.py
│   └── validation/
│       ├── models.py
│       └── validator_service.py
├── config.py
├── main.py            # Carga y validación de datos (ETL)
├── requirements.txt
└── .gitignore
```
---

## ⚙️ Instalación

### 1. Clonar repositorio

```bash
git clone https://github.com/djurado/fp-history.git
cd fp-history
```

---

### 2. Crear entorno virtual
```bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
```

---

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

---

## ▶️ Uso
```bash
streamlit run main.py
```

---

### 🌐 Modo local / remoto

El proyecto soporta dos modos de ejecución para manejar datos de forma segura:

| Modo | Descripción | Ruta de datos |
|------|-------------|---------------|
| `local`| Desarrollo local con datos privados | `datasets/privados/` |
| `remote`  (default) | Despliegue en Streamlit Cloud | `datasets/` |

#### Configuración mediante variable de entorno

```bash
# Modo local
export DATASETS_MODE=local
streamlit run main.py

# Modo remoto (para Streamlit Cloud)
export DATASETS_MODE=remote
streamlit run main.py
```

---

### 📂 Datos y metadata

Este proyecto NO incluye datos por defecto.

### 📁 datasets/

Ejemplo:
```
estadisticas_FP_2024_1.xlsx
estadisticas_FP_2024_2.xlsx
```

---

### 📁 metadata/

Archivo requerido:
```
metadata_estadisticas_FP.xlsx
```
Incluye:

	•	estructura de columnas
	•	valores máximos
	•	reglas de validación

---

### 🎨 Tecnologías
	•	Python
	•	Streamlit
	•	Pandas
	•	Plotly

