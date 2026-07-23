import os
import zipfile
import tempfile
import pandas as pd
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tablero GIS - Campo Escuela",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Visualizador de Parcelas - Campo Escuela")
st.markdown("Visualización e integración de capas de lotes y parcelas en formato KML y KMZ.")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# FUNCION PARA LEER TANTO KML COMO KMZ
# -----------------------------------------------------------------------------
def load_spatial_data(file_source) -> gpd.GeoDataFrame:
    """
    Lee archivos KML o KMZ y los convierte en un GeoDataFrame.
    """
    try:
        # 1. Si viene del uploader de Streamlit
        if hasattr(file_source, "name"):
            filename = file_source.name
            # Guardar temporalmente para que geopandas/pyogrio lo lea bien
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                tmp.write(file_source.getvalue())
                tmp_path = tmp.name
        else:
            filename = file_source
            tmp_path = file_source

        ext = os.path.splitext(filename)[1].lower()

        # Si es KML
        if ext == ".kml":
            gdf = gpd.read_file(tmp_path, driver="KML")

        # Si es KMZ (comprimido zip que contiene kml)
        elif ext == ".kmz":
            with zipfile.ZipFile(tmp_path, "r") as z:
                kml_filename = [f for f in z.namelist() if f.endswith(".kml")][0]
                with z.open(kml_filename) as kml_file:
                    gdf = gpd.read_file(kml_file, driver="KML")
        else:
            return gpd.GeoDataFrame()

        # Limpiar archivo temporal si se creó uno
        if hasattr(file_source, "name") and os.path.exists(tmp_path):
            os.remove(tmp_path)

        return gdf

    except Exception as e:
        st.error(f"Error al leer `{getattr(file_source, 'name', file_source)}`: {e}")
        return gpd.GeoDataFrame()


# -----------------------------------------------------------------------------
# SIDEBAR: Carga de Nuevos Archivos (KML o KMZ)
# -----------------------------------------------------------------------------
st.sidebar.header("📁 Cargar Nueva Parcela")
uploaded_file = st.sidebar.file_uploader("Sube un archivo KML o KMZ", type=["kml", "kmz"])

if uploaded_file is not None:
    save_path = os.path.join(DATA_DIR, uploaded_file.name)
    
    if not os.path.exists(save_path):
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.sidebar.success(f"Guardado exitosamente: `{uploaded_file.name}`")
    else:
        st.sidebar.info(f"El archivo `{uploaded_file.name}` ya existe en la base de datos.")


# -----------------------------------------------------------------------------
# LECTURA Y RENDERIZADO DE CAPAS
# -----------------------------------------------------------------------------
# Listar todos los KML y KMZ dentro de la carpeta 'data'
spatial_files = [
    f for f in os.listdir(DATA_DIR) 
    if f.lower().endswith(".kml") or f.lower().endswith(".kmz")
]

# Inicializar Mapa Base (Centrado inicial aproximado)
m = folium.Map(location=[-31.42, -64.18], zoom_start=13, tiles="OpenStreetMap")
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Google Satélite").add_to(m)

gdfs_to_bounds = []

if spatial_files:
    st.sidebar.subheader("🗂️ Capas Disponibles")
    
    for file_name in spatial_files:
        file_path = os.path.join(DATA_DIR, file_name)
        
        # Identificar si es la capa base del campo escuela
        is_base = "campo" in file_name.lower() or "lote" in file_name.lower()
        
        show_layer = st.sidebar.checkbox(
            f"{'📍 Base: ' if is_base else '🔹 '} {file_name}", 
            value=True
        )
        
        if show_layer:
            gdf = load_spatial_data(file_path)
            
            if not gdf.empty:
                gdfs_to_bounds.append(gdf)
                
                # Estilos visuales opcionales
                style_color = "#28a745" if is_base else "#ff7800"  # Verde para base, naranja para subidas
                
                folium.GeoJson(
                    gdf,
                    name=file_name,
                    style_function=lambda x, color=style_color: {
                        'fillColor': color,
                        'color': color,
                        'weight': 2,
                        'fillOpacity': 0.35
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=list(gdf.columns.drop('geometry', errors='ignore'))[:3]
                    ) if len(gdf.columns) > 1 else None
                ).add_to(m)

# Centrar y encuadrar automáticamente el mapa sobre todas las capas activas
if gdfs_to_bounds:
    combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs_to_bounds, ignore_index=True))
    bounds = combined_gdf.total_bounds  # [minx, miny, maxx, maxy]
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

folium.LayerControl().add_to(m)

# -----------------------------------------------------------------------------
# MOSTRAR MAPA
# -----------------------------------------------------------------------------
st_folium(m, width="100%", height=600)
