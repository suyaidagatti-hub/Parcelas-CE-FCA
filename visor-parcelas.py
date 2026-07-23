import os
import zipfile
import tempfile
import datetime
import pandas as pd
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Visor Campo Escuela (Solo Lectura)",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Visor de Parcelas - Campo Escuela")
st.markdown("Plataforma pública de visualización de lotes y parcelas. *(Modo Solo Lectura)*")

DATA_DIR = "data"


# -----------------------------------------------------------------------------
# FUNCIÓN PARA LEER KML / KMZ
# -----------------------------------------------------------------------------
def load_spatial_data(file_source) -> gpd.GeoDataFrame:
    """
    Lee archivos KML o KMZ y los convierte en un GeoDataFrame.
    """
    try:
        filename = file_source
        tmp_path = file_source

        ext = os.path.splitext(filename)[1].lower()

        if ext == ".kml":
            gdf = gpd.read_file(tmp_path, driver="KML")
        elif ext == ".kmz":
            with zipfile.ZipFile(tmp_path, "r") as z:
                kml_filename = [f for f in z.namelist() if f.endswith(".kml")][0]
                with z.open(kml_filename) as kml_file:
                    gdf = gpd.read_file(kml_file, driver="KML")
        else:
            return gpd.GeoDataFrame()

        return gdf

    except Exception as e:
        st.error(f"Error al leer `{file_source}`: {e}")
        return gpd.GeoDataFrame()


# -----------------------------------------------------------------------------
# GESTIÓN Y ORDENAMIENTO DE CAPAS
# -----------------------------------------------------------------------------
spatial_files = []
if os.path.exists(DATA_DIR):
    spatial_files = [
        f for f in os.listdir(DATA_DIR) 
        if f.lower().endswith(".kml") or f.lower().endswith(".kmz")
    ]

base_files = [f for f in spatial_files if "campo" in f.lower() or "lote" in f.lower()]
uploaded_files = [f for f in spatial_files if f not in base_files]

ordered_files = base_files + uploaded_files

# Mapa base
m = folium.Map(location=[-31.42, -64.18], zoom_start=13, tiles="OpenStreetMap")
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Google Satélite").add_to(m)

gdfs_to_bounds = []

if ordered_files:
    st.sidebar.title("🗂️ Capas del Campo")
    st.sidebar.markdown("Activa o desactiva la visibilidad de cada parcela:")
    
    for file_name in ordered_files:
        file_path = os.path.join(DATA_DIR, file_name)
        is_base = file_name in base_files
        
        show_layer = st.sidebar.checkbox(
            f"{'📍 Base: ' if is_base else '🔹 '} {file_name}", 
            value=True
        )
        
        if show_layer:
            gdf = load_spatial_data(file_path)
            
            if not gdf.empty:
                gdfs_to_bounds.append(gdf)
                
                if is_base:
                    style_color = "#28a745"  # Verde para base
                    fill_opacity = 0.25
                    weight = 2
                else:
                    style_color = "#ff3333"  # Rojo/Naranja para parcelas subidas
                    fill_opacity = 0.55
                    weight = 3

                folium.GeoJson(
                    gdf,
                    name=file_name,
                    style_function=lambda x, color=style_color, opacity=fill_opacity, w=weight: {
                        'fillColor': color,
                        'color': color,
                        'weight': w,
                        'fillOpacity': opacity
                    },
                    highlight_function=lambda x: {
                        'weight': 4,
                        'fillOpacity': 0.85
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=list(gdf.columns.drop('geometry', errors='ignore'))[:3],
                        sticky=True
                    ) if len(gdf.columns) > 1 else None
                ).add_to(m)

# Centrar mapa automáticamente sobre todas las capas activas
if gdfs_to_bounds:
    combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs_to_bounds, ignore_index=True))
    bounds = combined_gdf.total_bounds
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

folium.LayerControl().add_to(m)


# -----------------------------------------------------------------------------
# MOSTRAR MAPA
# -----------------------------------------------------------------------------
st_folium(m, width="100%", height=550)


# -----------------------------------------------------------------------------
# CONSULTA DE PARCELAS (DEBAJO DEL MAPA - SOLO LECTURA)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📋 Información de Parcelas Disponibles")

if not spatial_files:
    st.info("No hay capas ni parcelas cargadas actualmente.")
else:
    col1, col2, col3 = st.columns([4, 3, 3])
    col1.markdown("**Nombre del Archivo**")
    col2.markdown("**Tipo de Capa**")
    col3.markdown("**Fecha de Publicación**")
    st.markdown("---")

    for file_name in spatial_files:
        file_path = os.path.join(DATA_DIR, file_name)
        is_base = file_name in base_files
        
        mod_time = os.path.getmtime(file_path)
        fecha_carga = datetime.datetime.fromtimestamp(mod_time).strftime("%d/%m/%Y")
        
        c1, c2, c3 = st.columns([4, 3, 3])
        
        c1.text(f"📄 {file_name}")
        c2.caption("📍 Lote Base (Campo Escuela)" if is_base else "🔹 Parcela Integrada")
        c3.text(fecha_carga)
